from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from datetime import date
from typing import Protocol, TypeAlias

from rapidfuzz import fuzz, process
from pipeline.agenda_crosscheck import merge_ai_with_eagenda, parse_eagenda_items_from_file
from pipeline.agenda_legistar import fetch_legistar_agenda_items
from pipeline.lexicon import (
    contains_shared_agenda_boilerplate_phrase,
    is_contact_or_letterhead_noise,
    is_name_like_title,
    is_procedural_title,
)
from pipeline.models import Document, Catalog


logger = logging.getLogger("agenda-resolver")
AgendaItemRecord: TypeAlias = dict[str, object]
ResolvedAgendaPayload: TypeAlias = dict[str, object]


class AgendaExtractor(Protocol):
    def extract_agenda(self, content: str) -> list[AgendaItemRecord]: ...


class CatalogLike(Protocol):
    location: str | None
    content: str | None


class PlaceLike(Protocol):
    legistar_client: str | None


class EventLike(Protocol):
    record_date: date | None
    place: PlaceLike | None
    documents: Sequence[Document] | None


class DocumentLike(Protocol):
    event_id: int | None
    event: EventLike | None


class AgendaDocumentQuery(Protocol):
    def join(self, *args: object) -> "AgendaDocumentQuery": ...
    def filter(self, *args: object) -> "AgendaDocumentQuery": ...
    def all(self) -> list[Document]: ...


class AgendaResolverSession(Protocol):
    def query(self, model: type[Document]) -> AgendaDocumentQuery: ...


_LEGISTAR_PROCEDURAL_PATTERNS = [
    re.compile(r"(?i)^call to order$"),
    re.compile(r"(?i)^roll call$"),
    re.compile(r"(?i)^public participation(?: and access)?$"),
    re.compile(r"(?i)^public comment$"),
    re.compile(r"(?i)^adjourn(?:ment| special meeting| regular meeting)?$"),
    re.compile(r"(?i)^convene to closed session$"),
    re.compile(r"(?i)^\d{1,2}:\d{2}\s*(?:a\.m\.|p\.m\.|am|pm)\s+.*meeting.*$"),
]
_LEGISTAR_SECTION_WRAPPER_TITLES = {
    "approval of minutes",
    "postponements",
    "oral communications",
    "written communications",
    "consent calendar",
    "public hearings",
    "old business",
    "new business",
    "staff and commission reports",
    "future agenda setting",
}
_LEGISTAR_NOTICE_PATTERNS = [
    re.compile(r"(?i)\bteleconference\b"),
    re.compile(r"(?i)\bjoin the webinar\b"),
    re.compile(r"(?i)\bjoin by phone\b"),
    re.compile(r"(?i)\bmeeting id\b"),
    re.compile(r"(?i)\bpasscode\b"),
    re.compile(r"(?i)\braise hand\b"),
    re.compile(r"(?i)\bmembers? of the public\b"),
    re.compile(r"(?i)\bamericans with disabilities act\b"),
    re.compile(r"(?i)\bauxiliary aids\b"),
    re.compile(r"(?i)\bimportant notice\b"),
    re.compile(r"(?i)\bpublic records\b"),
    re.compile(r"(?i)\bwritten communications? sent\b"),
    re.compile(r"(?i)\byou may be limited to raising only those issues\b"),
    re.compile(r"(?i)\bquestions? on any items? in the agenda\b"),
    re.compile(r"(?i)\bthis portion of the meeting is reserved\b"),
    re.compile(r"(?i)\bunless there are separate discussions?\b"),
]


def _get_value(item: object, key: str) -> object | None:
    if isinstance(item, dict):
        return item.get(key)
    return getattr(item, key, None)


def _normalize_title(title: str) -> str:
    if title is None:
        raw = ""
    elif isinstance(title, str):
        raw = title
    else:
        # Some tests pass MagicMock placeholders for optional fields.
        raw = str(title)
    return re.sub(r"\s+", " ", raw).strip()


def _filter_legistar_items(items: list[AgendaItemRecord]) -> list[AgendaItemRecord]:
    """
    Remove portal wrapper rows so deterministic Legistar structure is graded on
    substantive agenda items instead of meeting scaffolding.
    """
    filtered: list[AgendaItemRecord] = []
    for item in items or []:
        title = _normalize_title(str(item.get("title") or ""))
        if not title:
            continue
        lowered = title.lower()
        if lowered.startswith("subject:"):
            filtered.append({**item, "title": title})
            continue
        if any(pattern.match(title) for pattern in _LEGISTAR_PROCEDURAL_PATTERNS):
            continue
        if lowered in _LEGISTAR_SECTION_WRAPPER_TITLES:
            continue
        if any(pattern.search(title) for pattern in _LEGISTAR_NOTICE_PATTERNS):
            continue
        if len(title) >= 180 and (
            "public hearing" not in lowered and "subject:" not in lowered and "application no" not in lowered
        ):
            continue
        filtered.append({**item, "title": title})
    return filtered


def _legistar_items_are_acceptable(items: list[AgendaItemRecord]) -> bool:
    if len(items) < 3:
        return False
    substantive_count = sum(
        1
        for item in items
        if not is_procedural_title(str(item.get("title") or ""))
        and not is_contact_or_letterhead_noise(
            str(item.get("title") or ""),
            str(item.get("description") or ""),
        )
    )
    return substantive_count >= 3


def agenda_quality_score(items: Sequence[object]) -> int:
    """
    Return a simple 0-100 quality score for agenda item title sets.
    """
    if not items:
        return 0

    score = 100
    seen = set()
    normalized_titles = []
    page_one_count = 0
    boilerplate_hits = 0
    procedural_hits = 0
    contact_hits = 0
    name_like_hits = 0

    for item in items:
        title = _normalize_title(str(_get_value(item, "title") or ""))
        page_number = _get_value(item, "page_number")

        if page_number in (None, 1):
            page_one_count += 1

        if not title:
            score -= 25
            continue

        key = title.lower()
        if key in seen:
            score -= 15
        seen.add(key)
        normalized_titles.append(key)

        if is_procedural_title(title):
            procedural_hits += 1
            score -= 14

        if is_contact_or_letterhead_noise(title, str(_get_value(item, "description") or "")):
            contact_hits += 1
            score -= 14

        # These patterns are common in meeting *headers* and legal notices, not agenda items.
        # We keep this generic and phrase-based (not city-specific) so it applies across jurisdictions.
        if contains_shared_agenda_boilerplate_phrase(title):
            boilerplate_hits += 1
            score -= 18

        # COVID-era meeting notices and similar advisories tend to be long prose, not agenda topics.
        if re.search(r"\bstate of emergency\b", key) and len(key) > 60:
            boilerplate_hits += 1
            score -= 12

        # Participation / teleconference / ADA notices are usually template boilerplate.
        if re.search(
            r"\b(teleconference|public participation|join the webinar|join by phone|e-?mail comments|raise hand|unmute|meeting id|passcode|ada|accommodation|auxiliary aids|interpreters?)\b",
            key,
        ):
            boilerplate_hits += 1
            score -= 10

        # Broadcast availability and "how to watch" notices are not agenda items.
        if re.search(
            r"\b(live captioned|captioned broadcasts?|broadcasts of council meetings|webcast|livestream|live stream|internet video stream|b-tv|channel 33|kpfa|radio 89\.3)\b",
            key,
        ):
            boilerplate_hits += 1
            score -= 10

        # Presentation/polling app instructions (e.g. Mentimeter) are not agenda items.
        if re.search(r"\b(mentimeter|slido|qr code|enter code|mobile device)\b", key):
            boilerplate_hits += 1
            score -= 10

        # Hybrid attendance participation blurbs are usually template noise.
        if re.search(r"\b(hybrid model|virtual attendance|attend this meeting)\b", key):
            boilerplate_hits += 1
            score -= 8

        # A pure person name (often from speaker lists) is rarely a useful agenda title.
        # Example: "Leslie Sakai" or "Kirk McCarthy (2)".
        if is_name_like_title(title):
            name_like_hits += 1
            score -= 10

        tokens = [t for t in key.split(" ") if t]
        if tokens:
            single_char_ratio = sum(1 for t in tokens if len(t) == 1 and t.isalpha()) / len(tokens)
            if single_char_ratio >= 0.6:
                score -= 20

        if re.search(r"(special closed meeting|calling a special meeting|city council)", key):
            score -= 12

        if len(title) < 6:
            score -= 15

        # Vote/result text is an optional confidence signal only.
        # We never require it, but if present it usually indicates a substantive item block.
        result_text = _normalize_title(str(_get_value(item, "result") or ""))
        if result_text:
            score += 2

    # If almost everything is on page 1, we likely lost page detection or are extracting headers.
    if page_one_count >= max(1, int(len(items) * 0.8)):
        score -= 20

    # If most "items" look like boilerplate or speaker names, treat the whole set as suspect.
    if len(items) >= 3:
        if boilerplate_hits >= 1 and boilerplate_hits >= int(len(items) * 0.34):
            score -= 15
        if procedural_hits >= max(1, int(len(items) * 0.34)):
            score -= 12
        if contact_hits >= max(1, int(len(items) * 0.25)):
            score -= 14
        if name_like_hits >= 2 and name_like_hits >= int(len(items) * 0.5):
            score -= 15

        # Duplicate-heavy sets often indicate TOC/body double extraction noise.
        unique_titles = len(set(normalized_titles))
        duplicate_ratio = 1.0 - (unique_titles / max(1, len(normalized_titles)))
        if duplicate_ratio >= 0.25:
            score -= 10

    return max(0, min(100, score))


def agenda_items_look_low_quality(items: Sequence[object]) -> bool:
    """
    Low-quality means likely extraction noise that should be regenerated.
    """
    if not items:
        return True
    return agenda_quality_score(items) < 45


def _best_html_items_for_event(
    session: AgendaResolverSession,
    catalog: CatalogLike,
    doc: DocumentLike | None,
) -> list[AgendaItemRecord]:
    html_candidates: list[list[AgendaItemRecord]] = []
    if doc is None:
        return []

    if catalog.location and str(catalog.location).lower().endswith(".html"):
        html_candidates.append(parse_eagenda_items_from_file(catalog.location))

    event_documents: Sequence[Document] | list[Document]
    event = getattr(doc, "event", None)
    if event and getattr(event, "documents", None) is not None:
        event_documents = [
            event_doc
            for event_doc in (event.documents or [])
            if getattr(getattr(event_doc, "catalog", None), "location", "")
            and str(event_doc.catalog.location).lower().endswith(".html")
        ]
    else:
        event_documents = (
            session.query(Document)
            .join(Catalog, Document.catalog_id == Catalog.id)
            .filter(
                Document.event_id == doc.event_id,
                Catalog.location.like("%.html"),
            )
            .all()
        )

    for html_doc in event_documents:
        if html_doc.catalog and html_doc.catalog.location:
            html_candidates.append(parse_eagenda_items_from_file(html_doc.catalog.location))

    if not html_candidates:
        return []

    # Use highest quality parsed HTML candidate.
    html_candidates = [items for items in html_candidates if items]
    if not html_candidates:
        return []
    return sorted(html_candidates, key=agenda_quality_score, reverse=True)[0]


def has_viable_structured_agenda_source(
    session: AgendaResolverSession,
    catalog: CatalogLike,
    doc: DocumentLike | None,
) -> bool:
    html_items = _best_html_items_for_event(session, catalog, doc)
    if len(html_items) >= 2 and agenda_quality_score(html_items) >= 55:
        return True

    legistar_client = None
    event_date = None
    if doc and doc.event and doc.event.place:
        legistar_client = doc.event.place.legistar_client
        event_date = doc.event.record_date

    legistar_items = fetch_legistar_agenda_items(legistar_client, event_date)
    filtered_legistar_items = _filter_legistar_items(legistar_items)
    return _legistar_items_are_acceptable(filtered_legistar_items)


def _apply_page_numbers_from_reference(
    primary_items: list[AgendaItemRecord],
    reference_items: list[AgendaItemRecord],
) -> list[AgendaItemRecord]:
    """
    Preserve deep-link quality by reusing page numbers from local extraction when possible.
    """
    if not primary_items or not reference_items:
        return primary_items

    title_to_page = {
        _normalize_title(str(item.get("title") or "")): item.get("page_number")
        for item in reference_items
        if _normalize_title(str(item.get("title") or "")) and item.get("page_number") not in (None, 0)
    }
    if not title_to_page:
        return primary_items

    for item in primary_items:
        if item.get("page_number") not in (None, 0):
            continue
        title = _normalize_title(str(item.get("title") or ""))
        if not title:
            continue
        match = process.extractOne(title, list(title_to_page.keys()), scorer=fuzz.token_sort_ratio)
        if match and match[1] >= 88:
            item["page_number"] = title_to_page[match[0]]

    return primary_items


def resolve_agenda_items(
    session: AgendaResolverSession,
    catalog: CatalogLike,
    doc: DocumentLike | None,
    local_ai: AgendaExtractor,
) -> ResolvedAgendaPayload:
    """
    Resolve agenda items in priority order:
    Legistar -> HTML -> LLM.
    """
    html_items = _best_html_items_for_event(session, catalog, doc)

    legistar_client = None
    event_date = None
    if doc and doc.event and doc.event.place:
        legistar_client = doc.event.place.legistar_client
        event_date = doc.event.record_date

    legistar_items = fetch_legistar_agenda_items(legistar_client, event_date)
    filtered_legistar_items = _filter_legistar_items(legistar_items)
    filtered_legistar_score = agenda_quality_score(filtered_legistar_items) if filtered_legistar_items else 0
    legistar_accepted = _legistar_items_are_acceptable(filtered_legistar_items)

    logger.info(
        "agenda_resolver_legistar catalog_location=%s raw_legistar_count=%s filtered_legistar_count=%s filtered_legistar_score=%s legistar_accepted=%s",
        getattr(catalog, "location", None),
        len(legistar_items),
        len(filtered_legistar_items),
        filtered_legistar_score,
        legistar_accepted,
    )

    if legistar_accepted:
        enriched = _apply_page_numbers_from_reference(filtered_legistar_items, html_items)
        return {
            "items": enriched,
            "source_used": "legistar",
            "quality_score": agenda_quality_score(enriched),
            "confidence": "high",
            "llm_fallback_invoked": False,
            "raw_legistar_count": len(legistar_items),
            "filtered_legistar_count": len(filtered_legistar_items),
            "legistar_accepted": True,
        }

    if len(html_items) >= 2 and agenda_quality_score(html_items) >= 55:
        return {
            "items": html_items,
            "source_used": "html",
            "quality_score": agenda_quality_score(html_items),
            "confidence": "medium",
            "llm_fallback_invoked": False,
            "raw_legistar_count": len(legistar_items),
            "filtered_legistar_count": len(filtered_legistar_items),
            "legistar_accepted": False,
        }

    llm_items = local_ai.extract_agenda(catalog.content) if catalog and catalog.content else []
    merged = merge_ai_with_eagenda(llm_items, html_items)
    quality_score = agenda_quality_score(merged)
    logger.debug(
        "agenda_resolver_fallback source=llm catalog_location=%s html_candidates=%s merged_items=%s quality_score=%s",
        getattr(catalog, "location", None),
        len(html_items),
        len(merged),
        quality_score,
    )
    return {
        "items": merged,
        "source_used": "llm",
        "quality_score": quality_score,
        "confidence": "medium" if merged else "low",
        "llm_fallback_invoked": True,
        "raw_legistar_count": len(legistar_items),
        "filtered_legistar_count": len(filtered_legistar_items),
        "legistar_accepted": False,
    }

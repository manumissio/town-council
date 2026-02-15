import re
from typing import Any, Dict, List

from rapidfuzz import fuzz, process

from pipeline.agenda_crosscheck import merge_ai_with_eagenda, parse_eagenda_items_from_file
from pipeline.agenda_legistar import fetch_legistar_agenda_items
from pipeline.models import Document, Catalog


def _get_value(item: Any, key: str):
    if isinstance(item, dict):
        return item.get(key)
    return getattr(item, key, None)


def _normalize_title(title: str) -> str:
    return re.sub(r"\s+", " ", (title or "")).strip()


def agenda_quality_score(items: List[Any]) -> int:
    """
    Return a simple 0-100 quality score for agenda item title sets.
    """
    if not items:
        return 0

    score = 100
    seen = set()
    page_one_count = 0
    boilerplate_hits = 0
    name_like_hits = 0

    for item in items:
        title = _normalize_title(_get_value(item, "title") or "")
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

        # These patterns are common in meeting *headers* and legal notices, not agenda items.
        # We keep this generic and phrase-based (not city-specific) so it applies across jurisdictions.
        if re.search(r"\b(i hereby request|in witness whereof|official seal|cause personal notice|forthwith)\b", key):
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
        if re.fullmatch(r"[A-Z][a-z]+(?: [A-Z]\.)?(?: [A-Z][a-z]+)+(?: \\(\\d+\\))?", title):
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

    # If almost everything is on page 1, we likely lost page detection or are extracting headers.
    if page_one_count >= max(1, int(len(items) * 0.8)):
        score -= 20

    # If most "items" look like boilerplate or speaker names, treat the whole set as suspect.
    if len(items) >= 3:
        if boilerplate_hits >= 1 and boilerplate_hits >= int(len(items) * 0.34):
            score -= 15
        if name_like_hits >= 2 and name_like_hits >= int(len(items) * 0.5):
            score -= 15

    return max(0, min(100, score))


def agenda_items_look_low_quality(items: List[Any]) -> bool:
    """
    Low-quality means likely extraction noise that should be regenerated.
    """
    if not items:
        return True
    return agenda_quality_score(items) < 45


def _best_html_items_for_event(session, catalog, doc):
    html_candidates = []

    if catalog.location and str(catalog.location).lower().endswith(".html"):
        html_candidates.append(parse_eagenda_items_from_file(catalog.location))

    html_docs = session.query(Document).join(Catalog, Document.catalog_id == Catalog.id).filter(
        Document.event_id == doc.event_id,
        Catalog.location.like('%.html')
    ).all()

    for html_doc in html_docs:
        if html_doc.catalog and html_doc.catalog.location:
            html_candidates.append(parse_eagenda_items_from_file(html_doc.catalog.location))

    if not html_candidates:
        return []

    # Use highest quality parsed HTML candidate.
    html_candidates = [items for items in html_candidates if items]
    if not html_candidates:
        return []
    return sorted(html_candidates, key=agenda_quality_score, reverse=True)[0]


def _apply_page_numbers_from_reference(primary_items: List[Dict[str, Any]], reference_items: List[Dict[str, Any]]):
    """
    Preserve deep-link quality by reusing page numbers from local extraction when possible.
    """
    if not primary_items or not reference_items:
        return primary_items

    title_to_page = {
        _normalize_title(item.get("title", "")): item.get("page_number")
        for item in reference_items
        if _normalize_title(item.get("title", "")) and item.get("page_number") not in (None, 0)
    }
    if not title_to_page:
        return primary_items

    for item in primary_items:
        if item.get("page_number") not in (None, 0):
            continue
        title = _normalize_title(item.get("title", ""))
        if not title:
            continue
        match = process.extractOne(title, list(title_to_page.keys()), scorer=fuzz.token_sort_ratio)
        if match and match[1] >= 88:
            item["page_number"] = title_to_page[match[0]]

    return primary_items


def resolve_agenda_items(session, catalog, doc, local_ai) -> Dict[str, Any]:
    """
    Resolve agenda items in priority order:
    Legistar -> HTML -> LLM.
    """
    llm_items = local_ai.extract_agenda(catalog.content) if catalog and catalog.content else []
    html_items = _best_html_items_for_event(session, catalog, doc)

    legistar_client = None
    event_date = None
    if doc and doc.event and doc.event.place:
        legistar_client = doc.event.place.legistar_client
        event_date = doc.event.record_date

    legistar_items = fetch_legistar_agenda_items(legistar_client, event_date)

    if len(legistar_items) >= 2 and agenda_quality_score(legistar_items) >= 55:
        enriched = _apply_page_numbers_from_reference(legistar_items, llm_items or html_items)
        return {
            "items": enriched,
            "source_used": "legistar",
            "quality_score": agenda_quality_score(enriched),
            "confidence": "high",
        }

    if len(html_items) >= 2 and agenda_quality_score(html_items) >= 55:
        return {
            "items": html_items,
            "source_used": "html",
            "quality_score": agenda_quality_score(html_items),
            "confidence": "medium",
        }

    merged = merge_ai_with_eagenda(llm_items, html_items)
    return {
        "items": merged,
        "source_used": "llm",
        "quality_score": agenda_quality_score(merged),
        "confidence": "medium" if merged else "low",
    }

from __future__ import annotations

import re

from pipeline.agenda_resolver_contracts import AgendaItemRecord
from pipeline.agenda_resolver_quality import _normalize_title
from pipeline.lexicon import is_contact_or_letterhead_noise, is_procedural_title


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

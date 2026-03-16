"""
Centralized lexical rules used across extraction, search, and trends.

Why this file exists:
- Procedural/noise lists were previously scattered across pipeline and API code.
- Centralizing them avoids logic drift between search/trends/summarization behavior.
"""

from __future__ import annotations

import re


PROCEDURAL_EXACT_TITLES = {
    "call to order",
    "roll call",
    "pledge of allegiance",
    "public comment",
    "adjournment",
    "closed session",
    "land acknowledgment",
    "land acknowledgement",
    "approval of minutes",
    "approval of the minutes",
    "approval of agenda",
    "approval of the agenda",
}

PROCEDURAL_ANCHORED_PATTERNS = (
    r"^public comment(?:\s+period)?$",
    r"^ceremonial matters$",
    r"^presentations?$",
    r"^announcements?$",
)

TREND_NOISE_TOPICS = {
    "roll call",
    "adjournment",
    "public comment",
    "consent calendar",
    "approval of minutes",
    "city manager",
    "city council",
    "staff report",
}

SHARED_AGENDA_BOILERPLATE_PATTERNS = (
    r"\b(communication access information)\b",
    r"\b(disability[- ]related|accommodation\(s\)|auxiliary aids|interpreters?)\b",
    r"\b(brown act|executive orders?)\b",
    r"\b(public comment portion|may participate in the public comment)\b",
    r"\b(agendas? and agenda reports?|agenda reports? may be accessed)\b",
    r"\b(questions regarding this matter)\b",
    r"\b(i hereby request|in witness whereof|official seal|cause personal notice|forthwith)\b",
)

SHARED_LEGAL_NOTICE_PATTERNS = (
    r"\b(i hereby request|in witness whereof|official seal|cause personal notice|forthwith)\b",
)

_NAME_LIKE_TITLE_RE = re.compile(r"[A-Z][a-z]+(?: [A-Z]\.)?(?: [A-Z][a-z]+)+(?:[-'][A-Za-z]+)?")
_NON_NAME_TITLE_TOKENS = {
    "access",
    "accommodation",
    "agenda",
    "agendas",
    "amendment",
    "appointment",
    "budget",
    "capital",
    "communication",
    "contract",
    "employee",
    "hearing",
    "improvement",
    "information",
    "network",
    "ordinance",
    "plan",
    "program",
    "project",
    "public",
    "reports",
    "resolution",
    "transit",
    "update",
    "zoning",
}

TEXT_REPAIR_CIVIC_LEXICON = {
    "A", "AN", "AND", "AS", "AT", "BY", "FOR", "FROM", "IN", "IS", "OF", "ON", "OR", "THE", "TO", "WITH", "WILL",
    "THIS", "THAT",
    "AGENDA", "ANNOTATED", "CITY", "COUNCIL", "MEETING", "SPECIAL", "PROCLAMATION", "CALLING",
    "SESSION", "REGULAR", "PUBLIC", "HEARING", "RESOLUTION", "ORDINANCE", "COMMISSION", "BOARD",
    "PLANNING", "ZONING", "ITEM", "CLOSED",
    "BERKELEY", "CUPERTINO", "PABLO", "AVENUE", "CORRIDORS", "CA",
}


def _as_text(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="ignore")
    return ""


def normalize_title_key(value: str) -> str:
    title = re.sub(r"\s+", " ", _as_text(value)).strip().lower()
    title = re.sub(r"^\s*(?:item\s*)?#?\s*\d+(?:\.\d+)?[\.\):]\s*", "", title)
    return title.strip(" -:\t")


def contains_shared_agenda_boilerplate_phrase(title: str) -> bool:
    normalized = re.sub(r"\s+", " ", _as_text(title)).strip().lower()
    if not normalized:
        return False
    return any(re.search(pattern, normalized) for pattern in SHARED_AGENDA_BOILERPLATE_PATTERNS)


def is_agenda_boilerplate_title(title: str) -> bool:
    normalized = re.sub(r"\s+", " ", _as_text(title)).strip()
    if not normalized:
        return True
    lowered = normalized.lower()
    if "http://" in lowered or "https://" in lowered or "www." in lowered:
        return True
    if contains_shared_agenda_boilerplate_phrase(normalized):
        return True
    return lowered.endswith(":") and len(lowered) <= 60


def is_name_like_title(title: str) -> bool:
    normalized = re.sub(r"\s+", " ", _as_text(title)).strip()
    if not normalized:
        return False
    tokens = [part.strip(".").lower() for part in normalized.split()]
    if any(token in _NON_NAME_TITLE_TOKENS for token in tokens):
        return False
    return bool(_NAME_LIKE_TITLE_RE.fullmatch(normalized))


def is_procedural_title(title: str, reject_enabled: bool = True) -> bool:
    if not reject_enabled:
        return False
    normalized = normalize_title_key(title)
    if not normalized:
        return True
    if normalized in PROCEDURAL_EXACT_TITLES:
        return True
    return any(re.match(pattern, normalized) for pattern in PROCEDURAL_ANCHORED_PATTERNS)


def is_contact_or_letterhead_noise(title: str, desc: str = "") -> bool:
    title_norm = re.sub(r"\s+", " ", _as_text(title)).strip().lower()
    desc_norm = re.sub(r"\s+", " ", _as_text(desc)).strip().lower()
    combined = f"{title_norm} {desc_norm}".strip()
    if not combined:
        return False

    if re.search(r"\b(tel|phone|fax|e-?mail|email|website)\s*:", combined):
        return True
    if re.search(r"\b[\w\.-]+@[\w\.-]+\.\w+\b", combined):
        return True
    if "http://" in combined or "https://" in combined or "www." in combined:
        return True
    if re.search(r"\b\d{3}[-\.\s]?\d{3}[-\.\s]?\d{4}\b", combined):
        return True
    if re.match(r"^\s*(from:|to:|cc:)\s*", title_norm):
        return True
    if re.search(r"\b\d{2,6}\s+[a-z][a-z\.\s]+(street|st|avenue|ave|road|rd|blvd|boulevard)\b", combined):
        return True
    if "office of the city manager" in combined:
        return True
    return False


def is_trend_noise_topic(topic: str) -> bool:
    normalized = re.sub(r"\s+", " ", _as_text(topic)).strip().lower()
    return normalized in TREND_NOISE_TOPICS

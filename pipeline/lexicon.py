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

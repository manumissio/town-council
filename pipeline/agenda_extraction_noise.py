from __future__ import annotations

import re

from pipeline.agenda_text_heuristics import (
    is_contact_or_letterhead_noise,
    is_procedural_noise_title,
    looks_like_agenda_segmentation_boilerplate,
    looks_like_teleconference_endpoint_line,
    normalize_spaces,
)
from pipeline.config import AGENDA_MIN_TITLE_CHARS
from pipeline.utils import is_likely_human_name


_WRAPPED_TITLE_BOUNDARY_RE = re.compile(
    r"(?i)^\s*(from|recommendation|recommended action|financial implications|contact|vote|result|action|subject)\s*:"
)
_WRAPPED_TITLE_LIST_ITEM_RE = re.compile(
    r"^\s*(?:item\s*)?#?\s*(\d{1,2}(?:\.\d+)?|[A-Z]|[IVXLC]+)[\.\):]\s+"
)
_DATE_LINE_RE = re.compile(r"^[A-Za-z]+,\s+[A-Za-z]+\s+\d{1,2},\s+\d{4}$")
_TIME_RE = re.compile(r"\b\d{1,2}:\d{2}\s*(?:a\.m\.|p\.m\.|am|pm)\b")
_ADDRESS_RE = re.compile(r"\b\d{2,6}\s+[A-Za-z].*(street|st|avenue|ave|road|rd|blvd|boulevard)\b")
_IP_ADDRESS_RE = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b")
_ACCESSIBILITY_RE = re.compile(r"\b(disability[- ]related|accommodation\(s\)|auxiliary aids|interpreters?)\b")
_BROWN_ACT_RE = re.compile(r"\b(brown act|executive orders?)\b")
_COMMUNICATION_ACCESS_RE = re.compile(r"\b(communication access information|questions regarding|public comment portion)\b")
_AGENDA_REPORTS_RE = re.compile(r"\b(agendas? and agenda reports?|agenda reports? may be accessed)\b")
_PUBLIC_COMMENT_RE = re.compile(r"\b(may participate in the public comment|meeting will be conducted in accordance)\b")
_BERKELEY_CITY_CLERK_RE = re.compile(r"\b(city clerk|cityofberkeley\.info|cityofberkeley\.org)\b")
_DISTRICT_RE = re.compile(r"^district\s+\d+\b")
_PERSON_NAME_BLOCKERS_RE = re.compile(
    r"\b(update|plan|zoning|hearing|budget|report|session|meeting|ordinance|resolution|project|communications|adjournment|amendment|specific|corridor|worksession)\b"
)
_NOISE_TITLE_TOKENS = (
    "special closed meeting",
    "calling a special meeting",
    "agenda packet",
    "table of contents",
    "supplemental communications",
    "form letters",
)


def is_noise_title(title: str) -> bool:
    lowered = normalize_spaces(title).lower()
    if not lowered or len(lowered) < AGENDA_MIN_TITLE_CHARS:
        return True
    if is_procedural_noise_title(lowered):
        return True
    if is_contact_or_letterhead_noise(lowered, ""):
        return True
    if _looks_like_link_or_endpoint_noise(lowered):
        return True
    if _looks_like_meeting_notice_noise(title, lowered):
        return True
    if _looks_like_legal_notice_noise(lowered):
        return True
    if any(token in lowered for token in _NOISE_TITLE_TOKENS):
        return True
    return bool(_DISTRICT_RE.match(lowered))


def looks_like_spaced_ocr(value: str) -> bool:
    tokens = [token for token in normalize_spaces(value).split(" ") if token]
    if not tokens:
        return False
    single_char_tokens = sum(1 for token in tokens if len(token) == 1 and token.isalpha())
    return (single_char_tokens / len(tokens)) >= 0.6


def is_probable_person_name(value: str) -> bool:
    clean = re.sub(r"\(\d+\)", "", normalize_spaces(value)).strip()
    if not clean:
        return False
    lowered = clean.lower()
    if "on behalf of" in lowered:
        return True
    if _PERSON_NAME_BLOCKERS_RE.search(lowered):
        return False
    if is_likely_human_name(clean, allow_single_word=True):
        return True
    return _looks_like_joined_person_names(clean, lowered)


def merge_wrapped_title_lines(base_title: str, block_text: str) -> str:
    title = normalize_spaces(base_title)
    if not block_text:
        return title

    added = 0
    for raw_line in (block_text or "").splitlines():
        line = raw_line.strip()
        if not line:
            if added > 0:
                break
            continue
        if _WRAPPED_TITLE_BOUNDARY_RE.match(line) or _WRAPPED_TITLE_LIST_ITEM_RE.match(line):
            break
        if len(line) < 3:
            break
        title = normalize_spaces(f"{title} {line}")
        added += 1
        if added >= 2:
            break
    return title


def _looks_like_link_or_endpoint_noise(lowered: str) -> bool:
    if _IP_ADDRESS_RE.search(lowered):
        return True
    if looks_like_teleconference_endpoint_line(lowered):
        return True
    if re.search(r"\b(us west|us east)\b", lowered):
        return True
    if looks_like_spaced_ocr(lowered):
        return True
    return lowered.startswith(("http://", "https://")) or "http://" in lowered or "https://" in lowered or "www." in lowered


def _looks_like_meeting_notice_noise(title: str, lowered: str) -> bool:
    if _DATE_LINE_RE.match(title):
        return True
    if _TIME_RE.search(lowered) or _ADDRESS_RE.search(lowered):
        return True
    if "mayor" in lowered or "councilmembers" in lowered:
        return True
    if lowered.endswith(":") and len(lowered) <= 45:
        return True
    return "as follows" in lowered and len(lowered) <= 40


def _looks_like_legal_notice_noise(lowered: str) -> bool:
    if looks_like_agenda_segmentation_boilerplate(lowered):
        return True
    if _ACCESSIBILITY_RE.search(lowered) or _BROWN_ACT_RE.search(lowered):
        return True
    if _COMMUNICATION_ACCESS_RE.search(lowered) or _AGENDA_REPORTS_RE.search(lowered):
        return True
    if _PUBLIC_COMMENT_RE.search(lowered) or _BERKELEY_CITY_CLERK_RE.search(lowered):
        return True
    if "government code section 84308" in lowered or "levine act" in lowered:
        return True
    return "parties to a proceeding involving a license, permit, or other" in lowered


def _looks_like_joined_person_names(clean: str, lowered: str) -> bool:
    if " and " not in lowered and " & " not in clean:
        return False
    tokens = re.split(r"\s+(?:and|&)\s+|\s+", clean)
    tokens = [token for token in tokens if token]
    return 2 <= len(tokens) <= 8 and all(re.match(r"^[A-Z][A-Za-z'’\.\-]*$", token) for token in tokens)

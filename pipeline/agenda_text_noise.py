from __future__ import annotations

import re
from typing import cast

from pipeline.agenda_text_noise_patterns import (
    ATTENDANCE_BOILERPLATE_FRAGMENTS,
    BOILERPLATE_FRAGMENT_GROUPS,
)
from pipeline.agenda_text_normalization import first_alpha_char, normalize_spaces
from pipeline.config import AGENDA_PROCEDURAL_REJECT_ENABLED
from pipeline.lexicon import (
    is_contact_or_letterhead_noise as lexicon_is_contact_or_letterhead_noise,
    is_procedural_title as lexicon_is_procedural_title,
)


def is_probable_line_fragment_title(title: str) -> bool:
    """
    Detect line-fragment titles from pleading-paper numbering/OCR artifacts.

    Why this is fallback-scoped:
    Heuristic fallback parsing sees raw lines like "16 in the appropriate ...".
    We only apply this trap there, not to direct LLM-parsed items.
    """
    normalized = normalize_spaces(title)
    if not normalized:
        return True

    alpha_char = first_alpha_char(normalized)
    if not alpha_char:
        return True

    lowered = normalized.lower()
    legislative_cues = (
        "subject:",
        "approve",
        "adopt",
        "permit",
        "ordinance",
        "resolution",
        "hearing",
        "zoning",
        "budget",
        "contract",
        "amendment",
    )
    if any(cue in lowered for cue in legislative_cues):
        return False

    return alpha_char.islower()


def is_procedural_noise_title(title: str) -> bool:
    """
    Return True for procedural placeholders that should not be treated as legislative items.

    Important: keep this precise. Broad substring matching (for example "approval")
    causes silent drops of substantive titles such as "Approval of Contract ...".
    """
    return cast(bool, lexicon_is_procedural_title(title, reject_enabled=AGENDA_PROCEDURAL_REJECT_ENABLED))


def is_contact_or_letterhead_noise(title: str, desc: str = "") -> bool:
    """
    Return True for contact/letterhead metadata commonly mis-read as agenda items.
    """
    return cast(bool, lexicon_is_contact_or_letterhead_noise(normalize_spaces(title), normalize_spaces(desc)))


def looks_like_attendance_boilerplate(line: str) -> bool:
    """
    Return True when a line is probably attendance/public-comment/ADA boilerplate.
    """
    if not line:
        return False

    lowered = line.strip().lower()

    if "http://" in lowered or "https://" in lowered or "www." in lowered:
        return True
    if re.search(r"\b[\w\.-]+@[\w\.-]+\.\w+\b", lowered):
        return True
    if re.search(r"\b\d{3}[-\.\s]?\d{3}[-\.\s]?\d{4}\b", lowered):
        return True
    if re.search(r"\bmeeting id\b|\bwebinar id\b|\bpasscode\b", lowered):
        return True

    return any(fragment in lowered for fragment in ATTENDANCE_BOILERPLATE_FRAGMENTS)


def looks_like_teleconference_endpoint_line(line: str) -> bool:
    """
    Return True for short endpoint-list lines that show up in teleconference instructions.
    """
    if not line:
        return False

    lowered = (line or "").strip().lower()
    match = re.match(r"^\s*(\d{2,3})\.(\d{2,3})(?:\.(\d{1,3}))?(?:\.(\d{1,3}))?\s*(.*)$", lowered)
    if not match:
        return False

    first_number = int(match.group(1))
    second_number = int(match.group(2))
    if first_number < 20 or second_number < 20:
        return False

    tail = (match.group(5) or "").strip()
    if not tail:
        return True
    return tail.startswith("(")


def looks_like_agenda_segmentation_boilerplate(line: str) -> bool:
    """
    Return True when a line is probably boilerplate that should not become an agenda item.
    """
    if not line:
        return False

    lowered = (line or "").strip().lower()
    compact = re.sub(r"[^a-z0-9]+", "", lowered)

    if looks_like_attendance_boilerplate(lowered):
        return True

    for fragments in BOILERPLATE_FRAGMENT_GROUPS:
        if any(fragment in lowered for fragment in fragments):
            return True
        compact_fragments = tuple(re.sub(r"[^a-z0-9]+", "", fragment) for fragment in fragments)
        if any(fragment and fragment in compact for fragment in compact_fragments):
            return True

    if "email address" in lowered:
        return True
    if "will not be disclosed" in lowered:
        return True
    if "connect to the meeting" in lowered:
        return True
    if "you may enter" in lowered and ("designation" in lowered or "resident" in lowered):
        return True
    if looks_like_teleconference_endpoint_line(lowered):
        return True
    return False


def looks_like_sub_marker_title(value: str) -> bool:
    """
    Detect likely nested list markers (A., 1a., i.) that often represent child rows.
    """
    title = normalize_spaces(value)
    return bool(re.match(r"^(?:[A-Z]\.|[0-9]{1,2}[a-z]\.|[ivxlcdm]+\.)\s+", title, flags=re.IGNORECASE))

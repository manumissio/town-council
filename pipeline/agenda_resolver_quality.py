from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
import re

from pipeline.lexicon import (
    contains_shared_agenda_boilerplate_phrase,
    is_contact_or_letterhead_noise,
    is_name_like_title,
    is_procedural_title,
)


def _get_value(item: object, key: str) -> object | None:
    if isinstance(item, dict):
        return item.get(key)
    return getattr(item, key, None)


def _normalize_title(title: object) -> str:
    if title is None:
        raw = ""
    elif isinstance(title, str):
        raw = title
    else:
        # Some tests pass MagicMock placeholders for optional fields.
        raw = str(title)
    return re.sub(r"\s+", " ", raw).strip()


@dataclass(slots=True)
class AgendaQualityCounts:
    page_one: int = 0
    boilerplate: int = 0
    procedural: int = 0
    contact: int = 0
    name_like: int = 0


def _score_title(title: str, description: str, result_text: str) -> tuple[int, AgendaQualityCounts]:
    counts = AgendaQualityCounts()
    if not title:
        return -25, counts
    key = title.lower()
    score_delta = 2 if result_text else 0
    if is_procedural_title(title):
        counts.procedural += 1
        score_delta -= 14
    if is_contact_or_letterhead_noise(title, description):
        counts.contact += 1
        score_delta -= 14
    boilerplate_penalty, boilerplate_hits = _boilerplate_score_delta(key, title)
    counts.boilerplate += boilerplate_hits
    score_delta += boilerplate_penalty
    if is_name_like_title(title):
        counts.name_like += 1
        score_delta -= 10
    if _has_spaced_letter_noise(key):
        score_delta -= 20
    if re.search(r"(special closed meeting|calling a special meeting|city council)", key):
        score_delta -= 12
    if len(title) < 6:
        score_delta -= 15
    return score_delta, counts


def _boilerplate_score_delta(key: str, title: str) -> tuple[int, int]:
    score_delta = 0
    hits = 0
    if contains_shared_agenda_boilerplate_phrase(title):
        hits += 1
        score_delta -= 18
    if re.search(r"\bstate of emergency\b", key) and len(key) > 60:
        hits += 1
        score_delta -= 12
    for pattern, penalty in _BOILERPLATE_PATTERNS:
        if re.search(pattern, key):
            hits += 1
            score_delta -= penalty
    return score_delta, hits


_BOILERPLATE_PATTERNS = (
    (
        r"\b(teleconference|public participation|join the webinar|join by phone|e-?mail comments|raise hand|unmute|meeting id|passcode|ada|accommodation|auxiliary aids|interpreters?)\b",
        10,
    ),
    (
        r"\b(live captioned|captioned broadcasts?|broadcasts of council meetings|webcast|livestream|live stream|internet video stream|b-tv|channel 33|kpfa|radio 89\.3)\b",
        10,
    ),
    (r"\b(mentimeter|slido|qr code|enter code|mobile device)\b", 10),
    (r"\b(hybrid model|virtual attendance|attend this meeting)\b", 8),
)


def _has_spaced_letter_noise(key: str) -> bool:
    tokens = [token for token in key.split(" ") if token]
    if not tokens:
        return False
    single_char_ratio = sum(1 for token in tokens if len(token) == 1 and token.isalpha()) / len(tokens)
    return single_char_ratio >= 0.6


def _apply_group_penalties(
    score: int,
    counts: AgendaQualityCounts,
    normalized_titles: list[str],
    *,
    item_count: int,
) -> int:
    if item_count < 3:
        return score
    if counts.boilerplate >= 1 and counts.boilerplate >= int(item_count * 0.34):
        score -= 15
    if counts.procedural >= max(1, int(item_count * 0.34)):
        score -= 12
    if counts.contact >= max(1, int(item_count * 0.25)):
        score -= 14
    if counts.name_like >= 2 and counts.name_like >= int(item_count * 0.5):
        score -= 15
    duplicate_ratio = 1.0 - (len(set(normalized_titles)) / max(1, len(normalized_titles)))
    if duplicate_ratio >= 0.25:
        score -= 10
    return score


def agenda_quality_score(items: Sequence[object]) -> int:
    """
    Return a simple 0-100 quality score for agenda item title sets.
    """
    if not items:
        return 0

    score = 100
    seen = set()
    normalized_titles = []
    counts = AgendaQualityCounts()

    for item in items:
        title = _normalize_title(str(_get_value(item, "title") or ""))
        page_number = _get_value(item, "page_number")

        if page_number in (None, 1):
            counts.page_one += 1

        if not title:
            score -= 25
            continue

        key = title.lower()
        if key in seen:
            score -= 15
        seen.add(key)
        normalized_titles.append(key)
        title_score, title_counts = _score_title(
            title,
            str(_get_value(item, "description") or ""),
            _normalize_title(str(_get_value(item, "result") or "")),
        )
        score += title_score
        counts.boilerplate += title_counts.boilerplate
        counts.procedural += title_counts.procedural
        counts.contact += title_counts.contact
        counts.name_like += title_counts.name_like

    if counts.page_one >= max(1, int(len(items) * 0.8)):
        score -= 20

    score = _apply_group_penalties(score, counts, normalized_titles, item_count=len(items))
    return max(0, min(100, score))


def agenda_items_look_low_quality(items: Sequence[object]) -> bool:
    """
    Low-quality means likely extraction noise that should be regenerated.
    """
    if not items:
        return True
    return agenda_quality_score(items) < 45

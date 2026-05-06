from __future__ import annotations

from collections.abc import Sequence
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

        # These patterns are common in meeting headers and legal notices, not agenda items.
        if contains_shared_agenda_boilerplate_phrase(title):
            boilerplate_hits += 1
            score -= 18

        if re.search(r"\bstate of emergency\b", key) and len(key) > 60:
            boilerplate_hits += 1
            score -= 12

        if re.search(
            r"\b(teleconference|public participation|join the webinar|join by phone|e-?mail comments|raise hand|unmute|meeting id|passcode|ada|accommodation|auxiliary aids|interpreters?)\b",
            key,
        ):
            boilerplate_hits += 1
            score -= 10

        if re.search(
            r"\b(live captioned|captioned broadcasts?|broadcasts of council meetings|webcast|livestream|live stream|internet video stream|b-tv|channel 33|kpfa|radio 89\.3)\b",
            key,
        ):
            boilerplate_hits += 1
            score -= 10

        if re.search(r"\b(mentimeter|slido|qr code|enter code|mobile device)\b", key):
            boilerplate_hits += 1
            score -= 10

        if re.search(r"\b(hybrid model|virtual attendance|attend this meeting)\b", key):
            boilerplate_hits += 1
            score -= 8

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

        result_text = _normalize_title(str(_get_value(item, "result") or ""))
        if result_text:
            score += 2

    if page_one_count >= max(1, int(len(items) * 0.8)):
        score -= 20

    if len(items) >= 3:
        if boilerplate_hits >= 1 and boilerplate_hits >= int(len(items) * 0.34):
            score -= 15
        if procedural_hits >= max(1, int(len(items) * 0.34)):
            score -= 12
        if contact_hits >= max(1, int(len(items) * 0.25)):
            score -= 14
        if name_like_hits >= 2 and name_like_hits >= int(len(items) * 0.5):
            score -= 15

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

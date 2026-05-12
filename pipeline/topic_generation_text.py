from __future__ import annotations

import re
from collections.abc import Callable
from importlib import import_module
from typing import Any, cast

from sqlalchemy.exc import SQLAlchemyError

from pipeline.topic_generation_contracts import PLACE_TOKEN_PATTERN


# These words appear constantly in city documents but are not useful topics.
CITY_STOP_WORDS = [
    "meeting",
    "council",
    "city",
    "minutes",
    "agenda",
    "present",
    "absent",
    "motion",
    "seconded",
    "voted",
    "item",
    "resolution",
    "ordinance",
    "approved",
    "unanimous",
    "quorum",
    "adjourned",
    "p.m.",
    "a.m.",
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "hereby",
    "thereof",
    "therein",
    "clerk",
    "mayor",
    "councilmember",
    "commission",
    "committee",
    "commissioner",
    "members",
    "teleconference",
    "staff",
    "report",
    "public",
    "comment",
    "called",
    "order",
    "action",
    "discussion",
    "held",
    "held",
    "carried",
    "aye",
    "noes",
    "abstain",
    "subject",
    "recommended",
    "recommendation",
    "http",
    "https",
    "www",
]


def _sanitize_text_for_topics(text: str) -> str:
    """
    Remove obvious extraction and URL noise before topic discovery.
    """
    if not text:
        return ""

    postprocess_extracted_text = cast(
        Callable[[str], str],
        getattr(import_module("pipeline.text_cleaning"), "postprocess_extracted_text"),
    )
    value = postprocess_extracted_text(text)
    value = re.sub(r"https?://\S+", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"www\.\S+", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"\bhttps?\b", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"\bwww\b", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"\[PAGE\s+\d+\]", " ", value, flags=re.IGNORECASE)
    return value


def _english_stop_words() -> frozenset[str]:
    from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS  # type: ignore[import-not-found, import-untyped]

    return cast(frozenset[str], ENGLISH_STOP_WORDS)


def _place_tokens(db: Any, place_id: int | None, place_model: Any) -> set[str]:
    if place_id is None:
        return set()
    try:
        place = db.get(place_model, place_id)
    except (SQLAlchemyError, RuntimeError, ValueError, AttributeError) as _place_error:
        return set()

    display = (getattr(place, "display_name", "") or getattr(place, "name", "") or "").lower()
    return set(re.findall(PLACE_TOKEN_PATTERN, display))


def _topic_stop_words(place_tokens: set[str] | None = None) -> list[str]:
    return sorted(set(CITY_STOP_WORDS).union(_english_stop_words()).union(place_tokens or set()))


def _normal_topic_title(topic: str) -> str:
    return topic.title()

from __future__ import annotations

import re

from pipeline.agenda_extraction_noise import is_noise_title
from pipeline.agenda_extraction_paragraphs import looks_like_nested_numeric_recommendation
from pipeline.agenda_text_heuristics import looks_like_agenda_segmentation_boilerplate


NUMBERED_LINE_PATTERN = re.compile(
    r"(?m)^\s*(?:item\s*)?#?\s*(\d{1,2}(?:\.\d+)?|[A-Z]|[IVXLC]+)[\.\):]\s+(.{6,400})$"
)
TOP_LEVEL_NUMERIC_RE = re.compile(r"\d{1,2}(?:\.\d+)?")
VOTE_RE = re.compile(r"(?im)\bVote:\s*([^\n\r]+)")
_RECOMMENDATION_SUBITEM_RE = re.compile(r"\d{1,2}[A-Za-z]")


def numbered_title_is_noise(title: str) -> bool:
    return is_noise_title(title) or looks_like_agenda_segmentation_boilerplate(title)


def is_contextual_subitem(
    marker: str,
    page_content: str,
    position: int,
    *,
    active_parent_item: str | None,
) -> bool:
    if active_parent_item is None:
        return False
    marker_upper = marker.upper()
    if re.fullmatch(r"[A-Z]", marker_upper) or re.fullmatch(r"[IVXLC]+", marker_upper):
        return True
    if re.fullmatch(_RECOMMENDATION_SUBITEM_RE, marker):
        return True
    return bool(TOP_LEVEL_NUMERIC_RE.fullmatch(marker) and looks_like_nested_numeric_recommendation(page_content, position))

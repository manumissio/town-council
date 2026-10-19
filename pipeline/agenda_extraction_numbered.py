from __future__ import annotations

import re

from pipeline.agenda_extraction_noise import is_noise_title
from pipeline.agenda_extraction_paragraphs import looks_like_nested_numeric_recommendation
from pipeline.agenda_extraction_parser import ITEM_FIELD_PATTERN, RECORD_ID_PATTERN
from pipeline.agenda_text_heuristics import looks_like_agenda_segmentation_boilerplate


TOP_LEVEL_NUMERIC_RE = re.compile(r"\d{1,2}(?:\.\d+)?")
VOTE_RE = re.compile(r"(?im)\bVote:\s*([^\n\r]+)")
_RECOMMENDATION_SUBITEM_RE = re.compile(r"(\d{1,2})\.?[A-Za-z]")


def is_numbered_business_marker(marker: str) -> bool:
    return bool(TOP_LEVEL_NUMERIC_RE.fullmatch(marker) or _RECOMMENDATION_SUBITEM_RE.fullmatch(marker))


def is_section_sibling(marker: str, parent_marker: str | None) -> bool:
    current = _RECOMMENDATION_SUBITEM_RE.fullmatch(marker)
    parent = _RECOMMENDATION_SUBITEM_RE.fullmatch(parent_marker or "")
    return bool(current and parent and current[1] == parent[1])


def numbered_item_title(match: re.Match[str]) -> str:
    title = match.group(2).strip()
    record_id = RECORD_ID_PATTERN.match(title)
    return title[record_id.end() :].strip() if record_id else title


def is_section_container(index: int, numbered_lines: list[re.Match[str]], page_content: str) -> bool:
    if index + 1 >= len(numbered_lines):
        return False
    current, following = numbered_lines[index : index + 2]
    marker = current.group(1).rstrip(".):")
    next_marker = following.group(1).rstrip(".):")
    if not marker.isdigit() or not current.group(2).strip().isupper():
        return False
    if ITEM_FIELD_PATTERN.search(page_content[current.end() : following.start()]):
        return False
    return next_marker.startswith(f"{marker}.") or bool(re.fullmatch(f"{marker}[A-Za-z]", next_marker))


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

from __future__ import annotations

import re

from pipeline.agenda_extraction_diagnostics import AgendaExtractionStats
from pipeline.agenda_extraction_noise import is_noise_title, is_probable_person_name
from pipeline.agenda_text_heuristics import (
    is_contact_or_letterhead_noise,
    is_procedural_noise_title,
    looks_like_agenda_segmentation_boilerplate,
    looks_like_end_marker_line,
    should_stop_after_marker,
)


_PAGE_MARKER_RE = re.compile(r"\[PAGE\s+(\d+)\]", flags=re.IGNORECASE)
_INLINE_PAGE_HEADER_RE = re.compile(r"(?im)^.*\bPage\s+(\d+)\s*$")
_NUMBERED_AGENDA_ITEM_AFTER_END_RE = re.compile(
    r"(?m)^\s*(?:item\s*)?#?\s*\d{1,2}(?:\.\d+)?[\.\):]\s+(.{6,400})$"
)
_LEGAL_TAIL_TITLE_RE = re.compile(r"\b(government code|notice was posted|ada accommodations?|accommodation)\b")


def split_text_by_page_markers(raw_text: str) -> list[tuple[int, str]]:
    markers = _page_markers(raw_text)
    if not markers:
        return [(1, raw_text)]

    chunks: list[tuple[int, str]] = []
    for index, (start_position, page_number) in enumerate(markers):
        end_position = markers[index + 1][0] if index + 1 < len(markers) else len(raw_text)
        chunk = raw_text[start_position:end_position].strip()
        if chunk:
            chunks.append((page_number, chunk))
    return chunks or [(1, raw_text)]


def truncate_page_after_end_marker(
    page_content: str,
    trailing_text: str,
    stats: AgendaExtractionStats,
) -> tuple[str, bool]:
    truncated_page_content = page_content
    stop_after_page = False
    lines = page_content.splitlines(keepends=True)
    cursor = 0
    for line_index, raw_line in enumerate(lines):
        candidate_line = raw_line.strip()
        line_length = len(raw_line)
        if not looks_like_end_marker_line(candidate_line):
            cursor += line_length
            continue
        stats.stop_marker_candidates += 1
        lookahead_window = "".join(lines[line_index : line_index + 25]) + "\n" + trailing_text[:2500]
        following_page_text = "".join(lines[line_index + 1 :])
        if should_stop_after_marker(candidate_line, lookahead_window) and not _has_agenda_item_after_end_marker(
            following_page_text
        ):
            truncated_page_content = page_content[:cursor]
            stats.stopped_after_end_marker += 1
            stop_after_page = True
            break
        cursor += line_length
    return truncated_page_content, stop_after_page


def page_has_speaker_context(page_content: str) -> bool:
    page_lower = page_content.lower()
    return (
        "communications" in page_lower
        or "speakers" in page_lower
        or "public comment" in page_lower
        or "item #1" in page_lower
        or "item #2" in page_lower
    )


def _has_agenda_item_after_end_marker(following_page_text: str) -> bool:
    for match in _NUMBERED_AGENDA_ITEM_AFTER_END_RE.finditer(following_page_text):
        if _post_marker_title_can_be_agenda_item(match.group(1).strip()):
            return True
    return False


def _post_marker_title_can_be_agenda_item(title: str) -> bool:
    if is_noise_title(title) or is_probable_person_name(title):
        return False
    if _LEGAL_TAIL_TITLE_RE.search(title.lower()):
        return False
    if is_procedural_noise_title(title) or is_contact_or_letterhead_noise(title, ""):
        return False
    return not looks_like_agenda_segmentation_boilerplate(title)


def _page_markers(raw_text: str) -> list[tuple[int, int]]:
    markers: list[tuple[int, int]] = []
    for match in _PAGE_MARKER_RE.finditer(raw_text):
        markers.append((match.start(), int(match.group(1))))
    for match in _INLINE_PAGE_HEADER_RE.finditer(raw_text):
        markers.append((match.start(), int(match.group(1))))
    markers.sort(key=lambda item: item[0])
    return _dedupe_nearby_page_markers(markers)


def _dedupe_nearby_page_markers(markers: list[tuple[int, int]]) -> list[tuple[int, int]]:
    deduped_markers: list[tuple[int, int]] = []
    for position, page_number in markers:
        if deduped_markers and deduped_markers[-1][1] == page_number and (position - deduped_markers[-1][0]) < 120:
            continue
        deduped_markers.append((position, page_number))
    return deduped_markers

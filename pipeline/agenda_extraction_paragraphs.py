from __future__ import annotations

import re

from pipeline.agenda_extraction_parser import ITEM_FIELD_PATTERN, RECORD_ID_PATTERN, iter_fallback_paragraphs
from pipeline.agenda_text_normalization import normalize_spaces


_PARAGRAPH_TITLE_PREFIX_RE = re.compile(r"^\s*\d+(?:\.\d+)?[\.\):]?\s*")
_PARAGRAPH_TITLE_BLOCKERS = ("page", "packet", "continuing")


def candidate_paragraphs(page_content: str) -> list[str]:
    source_paragraphs = iter_fallback_paragraphs(page_content)
    paragraphs: list[str] = []
    for index, paragraph in enumerate(source_paragraphs):
        record_id = RECORD_ID_PATTERN.fullmatch(paragraph.strip())
        if record_id and index and _eligible_paragraph(source_paragraphs[index - 1]):
            paragraphs[-1] = _attach_record_id(paragraphs[-1], paragraph.strip())
        elif not record_id and _eligible_paragraph(paragraph):
            paragraphs.append(paragraph)
    return paragraphs


def _eligible_paragraph(paragraph: str) -> bool:
    return 10 < len(paragraph.strip()) < 1000 and not RECORD_ID_PATTERN.fullmatch(paragraph.strip())


def _attach_record_id(paragraph: str, record_id: str) -> str:
    # The source paragraph is a boundary; a later ID cannot justify crossing it.
    title_end = _paragraph_title_end(paragraph)
    if not paragraph[:title_end].strip():
        return f"{paragraph}\n{record_id}"
    title = paragraph[:title_end]
    body = f"\n{paragraph[title_end:]}" if title_end < len(paragraph) else ""
    return f"{normalize_spaces(title)}{body}\n{record_id}"


def paragraph_has_record_anchor(paragraph: str) -> bool:
    title_end = _paragraph_title_end(paragraph)
    if not paragraph[:title_end].strip():
        return False
    # A body-field mention is not evidence that the paragraph is an item title.
    return bool(RECORD_ID_PATTERN.search(paragraph[:title_end])) or any(
        RECORD_ID_PATTERN.fullmatch(line.strip()) for line in paragraph[title_end:].splitlines()
    )


def _paragraph_title_end(paragraph: str) -> int:
    leading_field = ITEM_FIELD_PATTERN.match(paragraph)
    start = leading_field.end() if leading_field and leading_field.group(1).lower() == "subject" else 0
    body_field = ITEM_FIELD_PATTERN.search(paragraph, start)
    return body_field.start() if body_field else len(paragraph)


def paragraph_title(paragraph: str) -> str:
    title_text = paragraph[:_paragraph_title_end(paragraph)]
    if paragraph_has_record_anchor(paragraph):
        title_lines = [line for line in title_text.splitlines() if not RECORD_ID_PATTERN.fullmatch(line.strip())]
        return _PARAGRAPH_TITLE_PREFIX_RE.sub("", normalize_spaces(" ".join(title_lines)))
    lines = paragraph.splitlines()
    return _PARAGRAPH_TITLE_PREFIX_RE.sub("", lines[0].strip()) if lines else ""


def reject_paragraph_title(title: str) -> bool:
    title_lowered = title.lower()
    if not (10 < len(title) < 150):
        return True
    if any(blocker in title_lowered for blocker in _PARAGRAPH_TITLE_BLOCKERS):
        return True
    return title_lowered.startswith("item #")


def paragraph_description(paragraph: str) -> str:
    return (paragraph[:500] + "...") if len(paragraph) > 500 else paragraph


def paragraph_progress(before_count: int, after_count: int, added_count: int, reject_count: int) -> tuple[int, int]:
    if after_count > before_count:
        return added_count + 1, 0
    return added_count, reject_count + 1


def looks_like_nested_numeric_recommendation(page_content: str, position: int) -> bool:
    preceding_window = page_content[max(0, position - 500) : position].lower()
    return (
        "recommendation:" in preceding_window
        and ("would:" in preceding_window or "following action" in preceding_window)
        and "subject:" not in preceding_window[-160:]
    )

from __future__ import annotations

import re

from pipeline.agenda_extraction_parser import iter_fallback_paragraphs


_PARAGRAPH_TITLE_PREFIX_RE = re.compile(r"^\s*\d+(?:\.\d+)?[\.\):]?\s*")
_PARAGRAPH_TITLE_BLOCKERS = ("page", "packet", "continuing")


def candidate_paragraphs(page_content: str) -> list[str]:
    return [paragraph for paragraph in iter_fallback_paragraphs(page_content) if 10 < len(paragraph.strip()) < 1000]


def paragraph_title(paragraph: str) -> str:
    lines = paragraph.split("\n")
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

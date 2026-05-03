from __future__ import annotations

from pipeline.agenda_extraction_diagnostics import AgendaExtractionStats
from pipeline.agenda_extraction_noise import is_noise_title
from pipeline.agenda_text_heuristics import (
    is_contact_or_letterhead_noise,
    is_procedural_noise_title,
    is_probable_line_fragment_title,
    is_tabular_fragment,
    looks_like_agenda_segmentation_boilerplate,
    should_accept_llm_item,
)


def accept_agenda_item(
    title: str,
    description: str,
    page_number: int,
    source_type: str,
    context: dict[str, object] | None,
    *,
    mode: str,
    stats: AgendaExtractionStats,
) -> bool:
    if source_type == "fallback" and is_probable_line_fragment_title(title):
        stats.rejected_lowercase_fragment += 1
        return False
    if is_tabular_fragment(title, description, context):
        stats.rejected_tabular_fragment += 1
        return False
    if looks_like_agenda_segmentation_boilerplate(title):
        stats.rejected_notice_fragment += 1
        return False
    if is_noise_title(title):
        stats.rejected_noise += 1
        return False
    return _accept_llm_agenda_item(title, description, page_number, source_type, context, mode=mode, stats=stats)


def _accept_llm_agenda_item(
    title: str,
    description: str,
    page_number: int,
    source_type: str,
    context: dict[str, object] | None,
    *,
    mode: str,
    stats: AgendaExtractionStats,
) -> bool:
    if source_type != "llm":
        return True
    if is_procedural_noise_title(title):
        stats.rejected_procedural += 1
        return False
    if is_contact_or_letterhead_noise(title, description):
        stats.rejected_contact += 1
        return False
    if should_accept_llm_item(
        {"title": title, "description": description, "page_number": page_number, "context": context or {}},
        mode,
    ):
        return True
    stats.rejected_low_substance += 1
    return False

from __future__ import annotations

import logging
from dataclasses import dataclass

from pipeline.agenda_text_normalization import normalize_spaces


_EXTRACTION_COUNTERS_LOG = (
    "agenda_segmentation.counters mode=%s accepted_items_final=%s rejected_procedural=%s "
    "rejected_contact=%s rejected_low_substance=%s rejected_lowercase_fragment=%s "
    "rejected_notice_fragment=%s rejected_tabular_fragment=%s rejected_nested_subitem=%s "
    "context_carryover_pages=%s stop_marker_candidates=%s stopped_after_end_marker=%s "
    "rejected_noise=%s deduped_toc_duplicates=%s"
)


@dataclass(slots=True)
class AgendaExtractionStats:
    rejected_procedural: int = 0
    rejected_contact: int = 0
    rejected_low_substance: int = 0
    rejected_lowercase_fragment: int = 0
    rejected_notice_fragment: int = 0
    rejected_tabular_fragment: int = 0
    rejected_nested_subitem: int = 0
    context_carryover_pages: int = 0
    stop_marker_candidates: int = 0
    stopped_after_end_marker: int = 0
    rejected_noise: int = 0
    deduped_toc_duplicates: int = 0
    accepted_items_final: int = 0


@dataclass(slots=True)
class AgendaParseState:
    active_parent_item: str | None = None
    active_parent_page: int | None = None
    active_parent_marker: str | None = None
    parent_context_confidence: float = 0.0
    seen_top_level_items: int = 0
    person_heavy_numbered_list: bool = False

    def clear_parent(self) -> None:
        self.active_parent_item = None
        self.active_parent_page = None
        self.active_parent_marker = None
        self.parent_context_confidence = 0.0

    def remember_parent(self, title: str, page_number: int, marker: str) -> None:
        self.active_parent_item = normalize_spaces(title)
        self.active_parent_page = page_number
        self.active_parent_marker = marker
        self.parent_context_confidence = 1.0
        self.seen_top_level_items += 1

    def item_context(self) -> dict[str, object]:
        return {
            "has_active_parent": self.active_parent_item is not None,
            "parent_context_confidence": self.parent_context_confidence,
            "seen_top_level_items": self.seen_top_level_items,
        }


def log_agenda_extraction_counters(
    logger: logging.Logger,
    *,
    mode: str,
    stats: AgendaExtractionStats,
) -> None:
    logger.info(
        _EXTRACTION_COUNTERS_LOG,
        mode,
        stats.accepted_items_final,
        stats.rejected_procedural,
        stats.rejected_contact,
        stats.rejected_low_substance,
        stats.rejected_lowercase_fragment,
        stats.rejected_notice_fragment,
        stats.rejected_tabular_fragment,
        stats.rejected_nested_subitem,
        stats.context_carryover_pages,
        stats.stop_marker_candidates,
        stats.stopped_after_end_marker,
        stats.rejected_noise,
        stats.deduped_toc_duplicates,
    )

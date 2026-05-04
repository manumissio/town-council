import logging

from pipeline.agenda_summary_items import AgendaSummaryItem
from pipeline.agenda_summary_scaffold import AgendaSummaryScaffold


AGENDA_SUMMARY_COUNTERS_LOG = (
    "agenda_summary.counters total_items=%s kept_items=%s summary_filtered_notice_fragments=%s "
    "agenda_summary_items_total=%s agenda_summary_items_included=%s agenda_summary_items_truncated=%s "
    "agenda_summary_input_chars=%s agenda_summary_single_item_mode=%s agenda_summary_unknowns_count=%s"
)
AGENDA_SUMMARY_FALLBACK_LOG = "agenda_summary.counters agenda_summary_fallback_deterministic=%s"
AGENDA_SUMMARY_GROUNDING_PRUNED_LOG = "agenda_summary.counters agenda_summary_grounding_pruned_lines=%s"


def build_summary_counters(
    structured_items: list[AgendaSummaryItem],
    filtered_items: list[AgendaSummaryItem],
    scaffold: AgendaSummaryScaffold,
    truncation_meta: dict[str, int] | None,
) -> dict[str, int]:
    return {
        "agenda_summary_items_total": len(structured_items),
        "agenda_summary_items_included": len(filtered_items),
        "agenda_summary_items_truncated": int((truncation_meta or {}).get("items_truncated", 0)),
        "agenda_summary_input_chars": int((truncation_meta or {}).get("input_chars", 0)),
        "agenda_summary_single_item_mode": int(bool(scaffold.get("single_item_mode"))),
        "agenda_summary_unknowns_count": len(scaffold.get("unknowns", [])),
        "agenda_summary_grounding_pruned_lines": 0,
        "agenda_summary_fallback_deterministic": 0,
    }


def log_summary_counters(
    *,
    logger: logging.Logger,
    total_items: int,
    filtered_items: int,
    filtered_notice_fragments: int,
    counters: dict[str, int],
) -> None:
    logger.info(
        AGENDA_SUMMARY_COUNTERS_LOG,
        total_items,
        filtered_items,
        filtered_notice_fragments,
        counters["agenda_summary_items_total"],
        counters["agenda_summary_items_included"],
        counters["agenda_summary_items_truncated"],
        counters["agenda_summary_input_chars"],
        counters["agenda_summary_single_item_mode"],
        counters["agenda_summary_unknowns_count"],
    )


def log_deterministic_fallback(logger: logging.Logger, counters: dict[str, int]) -> None:
    counters["agenda_summary_fallback_deterministic"] = 1
    logger.info(AGENDA_SUMMARY_FALLBACK_LOG, 1)


def log_grounding_pruned_lines(logger: logging.Logger, removed_count: int) -> None:
    logger.info(AGENDA_SUMMARY_GROUNDING_PRUNED_LOG, removed_count)

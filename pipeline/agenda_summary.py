import logging
from dataclasses import dataclass
from typing import Any, Callable

from pipeline.config import (
    AGENDA_SUMMARY_MAX_BULLETS,
    AGENDA_SUMMARY_TEMPERATURE,
    LLM_SUMMARY_MAX_TOKENS,
)
from pipeline.summary_quality import is_summary_grounded, prune_unsupported_summary_lines


logger = logging.getLogger("local-ai")

AGENDA_SUMMARY_COUNTERS_LOG = (
    "agenda_summary.counters total_items=%s kept_items=%s summary_filtered_notice_fragments=%s "
    "agenda_summary_items_total=%s agenda_summary_items_included=%s agenda_summary_items_truncated=%s "
    "agenda_summary_input_chars=%s agenda_summary_single_item_mode=%s agenda_summary_unknowns_count=%s"
)
AGENDA_SUMMARY_FALLBACK_LOG = "agenda_summary.counters agenda_summary_fallback_deterministic=%s"
AGENDA_SUMMARY_GROUNDING_PRUNED_LOG = "agenda_summary.counters agenda_summary_grounding_pruned_lines=%s"


@dataclass(frozen=True)
class AgendaSummaryHelpers:
    coerce_item: Callable[[Any, int], dict]
    should_drop_item: Callable[[str], bool]
    build_scaffold: Callable[[list[dict], dict | None], dict]
    build_prompt: Callable[[str, str, list[dict], dict, dict | None], str]
    source_text: Callable[[list[dict]], str]
    normalize_output: Callable[[str, dict], str]
    deterministic_summary: Callable[[list[Any], int, dict | None], str]
    is_too_short: Callable[[str], bool]


def _serialize_item_for_filtering(item: dict) -> str:
    serialized = item.get("title", "")
    if item.get("description"):
        serialized = f"{serialized} - {item['description']}"
    return serialized


def _filter_summary_items(
    structured_items: list[dict],
    should_drop_item: Callable[[str], bool],
) -> tuple[list[dict], int]:
    filtered_items: list[dict] = []
    filtered_notice_fragments = 0
    for item in structured_items:
        if should_drop_item(_serialize_item_for_filtering(item)):
            filtered_notice_fragments += 1
            continue
        filtered_items.append(item)
    return filtered_items, filtered_notice_fragments


def _build_summary_counters(
    structured_items: list[dict],
    filtered_items: list[dict],
    scaffold: dict,
    truncation_meta: dict | None,
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


def _log_summary_counters(
    *,
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


def _log_deterministic_fallback(counters: dict[str, int]) -> None:
    counters["agenda_summary_fallback_deterministic"] = 1
    logger.info(AGENDA_SUMMARY_FALLBACK_LOG, 1)


def run_agenda_summary_pipeline(
    provider: Any,
    *,
    meeting_title: str,
    meeting_date: str,
    items: list[Any] | None,
    truncation_meta: dict | None,
    helpers: AgendaSummaryHelpers,
) -> str:
    structured_items = [helpers.coerce_item(item, i) for i, item in enumerate(items or [])]
    filtered_items, filtered_notice_fragments = _filter_summary_items(
        structured_items,
        helpers.should_drop_item,
    )
    scaffold = helpers.build_scaffold(filtered_items, truncation_meta)
    counters = _build_summary_counters(
        structured_items,
        filtered_items,
        scaffold,
        truncation_meta,
    )
    _log_summary_counters(
        total_items=len(structured_items),
        filtered_items=len(filtered_items),
        filtered_notice_fragments=filtered_notice_fragments,
        counters=counters,
    )

    if not filtered_items:
        _log_deterministic_fallback(counters)
        return helpers.deterministic_summary([], AGENDA_SUMMARY_MAX_BULLETS, truncation_meta)

    prompt = helpers.build_prompt(
        meeting_title,
        meeting_date,
        filtered_items,
        scaffold,
        truncation_meta,
    )
    grounding_source = helpers.source_text(filtered_items)
    raw_summary = (
        provider.summarize_agenda_items(
            prompt,
            max_tokens=LLM_SUMMARY_MAX_TOKENS,
            temperature=AGENDA_SUMMARY_TEMPERATURE,
        )
        or ""
    ).strip()
    cleaned_summary = helpers.normalize_output(raw_summary, scaffold)

    pruned_summary, removed_count = prune_unsupported_summary_lines(cleaned_summary, grounding_source)
    counters["agenda_summary_grounding_pruned_lines"] = int(removed_count)
    if removed_count:
        logger.info(AGENDA_SUMMARY_GROUNDING_PRUNED_LOG, removed_count)
    cleaned_summary = pruned_summary or cleaned_summary

    grounded_summary = is_summary_grounded(cleaned_summary, grounding_source)
    if (not grounded_summary.is_grounded) or helpers.is_too_short(cleaned_summary):
        _log_deterministic_fallback(counters)
        return helpers.deterministic_summary(
            filtered_items,
            AGENDA_SUMMARY_MAX_BULLETS,
            truncation_meta,
        )
    return cleaned_summary

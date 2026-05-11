from __future__ import annotations

from collections.abc import Callable, Mapping

from pipeline.backlog_maintenance import (
    AGENDA_SUMMARY_BUNDLE_BUILD_MS,
    AGENDA_SUMMARY_EMBED_DISPATCH_MS,
    AGENDA_SUMMARY_PERSIST_MS,
    AGENDA_SUMMARY_REINDEX_MS,
    AGENDA_SUMMARY_RENDER_MS,
)
from pipeline.task_runtime import logger


def initial_summary_backfill_counts(*, selected: int) -> dict[str, int]:
    return {
        "selected": selected,
        "complete": 0,
        "changed_catalogs": 0,
        "cached": 0,
        "stale": 0,
        "blocked_low_signal": 0,
        "blocked_ungrounded": 0,
        "not_generated_yet": 0,
        "error": 0,
        "other": 0,
        "agenda_deterministic_complete": 0,
        "llm_complete": 0,
        "deterministic_fallback_complete": 0,
        "reindexed": 0,
        "reindex_failed": 0,
        "embed_enqueued": 0,
        "embed_dispatch_failed": 0,
        AGENDA_SUMMARY_BUNDLE_BUILD_MS: 0,
        AGENDA_SUMMARY_RENDER_MS: 0,
        AGENDA_SUMMARY_PERSIST_MS: 0,
        AGENDA_SUMMARY_REINDEX_MS: 0,
        AGENDA_SUMMARY_EMBED_DISPATCH_MS: 0,
    }


SummaryProgressCallback = Callable[[dict[str, object]], None]


def _count_value(raw_count: object) -> int:
    if not raw_count:
        return 0
    return int(raw_count)


def _text_value(raw_text: object) -> str:
    if raw_text is None:
        return ""
    return str(raw_text)


def _mapping_value(raw_mapping: object) -> Mapping[str, object]:
    if isinstance(raw_mapping, Mapping):
        return raw_mapping
    return {}


def finish_empty_summary_backfill(
    counts: dict[str, int],
    progress_callback: SummaryProgressCallback | None,
) -> None:
    logger.info("summary_hydration_backfill selected=0")
    if progress_callback:
        progress_callback(
            {
                "event_type": "stage_finish",
                "stage": "summary",
                "counts": counts.copy(),
                "detail": {"selected": 0},
            }
        )


def emit_summary_stage_start(
    counts: dict[str, int],
    selected_count: int,
    progress_callback: SummaryProgressCallback | None,
) -> None:
    if progress_callback:
        progress_callback(
            {
                "event_type": "stage_start",
                "stage": "summary",
                "counts": counts.copy(),
                "detail": {"selected": selected_count},
            }
        )


def add_agenda_batch_counts(counts: dict[str, int], agenda_batch: Mapping[str, object]) -> None:
    reindex_summary = _mapping_value(agenda_batch.get("reindex_summary"))
    counts["reindexed"] += _count_value(reindex_summary.get("catalogs_reindexed"))
    counts["reindex_failed"] += _count_value(reindex_summary.get("catalogs_failed"))
    embed_summary = _mapping_value(agenda_batch.get("embed_summary"))
    counts["embed_enqueued"] += _count_value(embed_summary.get("embed_enqueued"))
    counts["embed_dispatch_failed"] += _count_value(embed_summary.get("embed_dispatch_failed"))
    agenda_summary_timings = _mapping_value(agenda_batch.get("agenda_summary_timings"))
    for metric_name in (
        AGENDA_SUMMARY_BUNDLE_BUILD_MS,
        AGENDA_SUMMARY_RENDER_MS,
        AGENDA_SUMMARY_PERSIST_MS,
        AGENDA_SUMMARY_REINDEX_MS,
        AGENDA_SUMMARY_EMBED_DISPATCH_MS,
    ):
        counts[metric_name] += _count_value(agenda_summary_timings.get(metric_name))


def record_summary_result_counts(counts: dict[str, int], summary_result: Mapping[str, object]) -> None:
    status = _text_value(summary_result.get("status")) or "other"
    counts[status if status in counts else "other"] += 1
    counts["changed_catalogs"] += int(bool(summary_result.get("changed")))
    counts["reindexed"] += _count_value(summary_result.get("reindexed"))
    counts["reindex_failed"] += _count_value(summary_result.get("reindex_failed"))
    counts["embed_enqueued"] += _count_value(summary_result.get("embed_enqueued"))
    counts["embed_dispatch_failed"] += _count_value(summary_result.get("embed_dispatch_failed"))
    completion_mode = _text_value(summary_result.get("completion_mode"))
    if completion_mode == "agenda_deterministic":
        counts["agenda_deterministic_complete"] += 1
    elif completion_mode == "llm":
        counts["llm_complete"] += 1
    elif completion_mode == "deterministic_fallback":
        counts["deterministic_fallback_complete"] += 1


def emit_summary_progress(
    *,
    catalog_ids: list[int],
    index: int,
    catalog_id: int,
    counts: dict[str, int],
    summary_result: Mapping[str, object],
    progress_callback: SummaryProgressCallback | None,
    progress_every: int,
) -> None:
    if not progress_callback or not (index == 1 or index % progress_every == 0 or index == len(catalog_ids)):
        return
    progress_callback(
        {
            "event_type": "progress",
            "stage": "summary",
            "counts": counts.copy(),
            "last_catalog_id": catalog_id,
            "detail": {
                "done": index,
                "total": len(catalog_ids),
                "last_status": _text_value(summary_result.get("status")) or "other",
                "completion_mode": _text_value(summary_result.get("completion_mode")),
                "error": _text_value(summary_result.get("error")),
            },
        }
    )

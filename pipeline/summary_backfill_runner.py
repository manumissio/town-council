from __future__ import annotations

from typing import Any, Callable

from pipeline.backlog_maintenance import (
    AGENDA_SUMMARY_BUNDLE_BUILD_MS,
    AGENDA_SUMMARY_EMBED_DISPATCH_MS,
    AGENDA_SUMMARY_PERSIST_MS,
    AGENDA_SUMMARY_REINDEX_MS,
    AGENDA_SUMMARY_RENDER_MS,
    build_deterministic_agenda_summary_payload,
    build_deterministic_agenda_summary_payloads,
    summarize_catalog_with_maintenance_mode,
    summary_timeout_override,
)
from pipeline.indexer import reindex_catalog, reindex_catalogs
from pipeline.semantic_tasks import embed_catalog_task
from pipeline.summary_backfill_dispatch import enqueue_embed_catalogs
from pipeline.summary_backfill_logging import log_backfill_counts
from pipeline.summary_backfill_queries import (
    select_catalog_ids_for_summary_hydration,
    summary_doc_kind_map,
)
from pipeline.task_runtime import logger, task_session


def run_summary_hydration_backfill(
    force: bool = False,
    limit: int | None = None,
    city: str | None = None,
    *,
    summary_timeout_seconds: int | None = None,
    summary_fallback_mode: str = "none",
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
    progress_every: int = 25,
    generate_summary_callable: Callable[[int], dict[str, Any]],
    agenda_embed_callback: Callable[[list[int]], dict[str, object]] = enqueue_embed_catalogs,
    session_factory: Callable[[], Any] = task_session,
    select_catalog_ids_callable: Callable[
        [Any, int | None, str | None], list[int]
    ] = select_catalog_ids_for_summary_hydration,
    summary_doc_kind_map_callable: Callable[[Any, list[int]], dict[int, str]] = summary_doc_kind_map,
    agenda_summary_batch_builder: Callable[..., dict[str, Any]] = build_deterministic_agenda_summary_payloads,
    summarize_catalog_callable: Callable[..., dict[str, Any]] = summarize_catalog_with_maintenance_mode,
) -> dict[str, int]:
    """
    Generate summaries once across the current eligible backlog snapshot.
    """
    catalog_ids = _select_catalog_ids(
        session_factory=session_factory,
        select_catalog_ids_callable=select_catalog_ids_callable,
        limit=limit,
        city=city,
    )
    counts = _initial_counts(selected=len(catalog_ids))
    if not catalog_ids:
        _finish_empty_backfill(counts, progress_callback)
        return counts

    _emit_stage_start(counts, len(catalog_ids), progress_callback)
    doc_kind_by_catalog_id = _load_doc_kind_map(
        session_factory=session_factory,
        summary_doc_kind_map_callable=summary_doc_kind_map_callable,
        catalog_ids=catalog_ids,
    )
    agenda_results = _run_agenda_batch(
        catalog_ids=catalog_ids,
        doc_kind_by_catalog_id=doc_kind_by_catalog_id,
        counts=counts,
        agenda_summary_batch_builder=agenda_summary_batch_builder,
        agenda_embed_callback=agenda_embed_callback,
    )
    _run_backfill_loop(
        catalog_ids=catalog_ids,
        agenda_results=agenda_results,
        counts=counts,
        summary_timeout_seconds=summary_timeout_seconds,
        summary_fallback_mode=summary_fallback_mode,
        progress_callback=progress_callback,
        progress_every=progress_every,
        generate_summary_callable=generate_summary_callable,
        summarize_catalog_callable=summarize_catalog_callable,
    )
    log_backfill_counts(counts)
    if progress_callback:
        progress_callback({"event_type": "stage_finish", "stage": "summary", "counts": counts.copy()})
    return counts


def _initial_counts(*, selected: int) -> dict[str, int]:
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


def _select_catalog_ids(
    *,
    session_factory: Callable[[], Any],
    select_catalog_ids_callable: Callable[[Any, int | None, str | None], list[int]],
    limit: int | None,
    city: str | None,
) -> list[int]:
    db = session_factory()
    try:
        return select_catalog_ids_callable(db, limit, city)
    finally:
        db.close()


def _finish_empty_backfill(
    counts: dict[str, int],
    progress_callback: Callable[[dict[str, Any]], None] | None,
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


def _emit_stage_start(
    counts: dict[str, int],
    selected_count: int,
    progress_callback: Callable[[dict[str, Any]], None] | None,
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


def _load_doc_kind_map(
    *,
    session_factory: Callable[[], Any],
    summary_doc_kind_map_callable: Callable[[Any, list[int]], dict[int, str]],
    catalog_ids: list[int],
) -> dict[int, str]:
    db = session_factory()
    try:
        return summary_doc_kind_map_callable(db, catalog_ids)
    finally:
        db.close()


def _run_agenda_batch(
    *,
    catalog_ids: list[int],
    doc_kind_by_catalog_id: dict[int, str],
    counts: dict[str, int],
    agenda_summary_batch_builder: Callable[..., dict[str, Any]],
    agenda_embed_callback: Callable[[list[int]], dict[str, object]],
) -> dict[int, dict[str, Any]]:
    agenda_catalog_ids = [
        catalog_id for catalog_id in catalog_ids if doc_kind_by_catalog_id.get(catalog_id) == "agenda"
    ]
    if not agenda_catalog_ids:
        return {}
    agenda_batch = agenda_summary_batch_builder(
        agenda_catalog_ids,
        reindex_callback=reindex_catalogs,
        embed_callback=agenda_embed_callback,
    )
    _add_agenda_batch_counts(counts, agenda_batch)
    return dict(agenda_batch.get("results") or {})


def _add_agenda_batch_counts(counts: dict[str, int], agenda_batch: dict[str, Any]) -> None:
    reindex_summary = agenda_batch.get("reindex_summary") or {}
    counts["reindexed"] += int(reindex_summary.get("catalogs_reindexed") or 0)
    counts["reindex_failed"] += int(reindex_summary.get("catalogs_failed") or 0)
    embed_summary = agenda_batch.get("embed_summary") or {}
    counts["embed_enqueued"] += int(embed_summary.get("embed_enqueued") or 0)
    counts["embed_dispatch_failed"] += int(embed_summary.get("embed_dispatch_failed") or 0)
    agenda_summary_timings = agenda_batch.get("agenda_summary_timings") or {}
    for metric_name in (
        AGENDA_SUMMARY_BUNDLE_BUILD_MS,
        AGENDA_SUMMARY_RENDER_MS,
        AGENDA_SUMMARY_PERSIST_MS,
        AGENDA_SUMMARY_REINDEX_MS,
        AGENDA_SUMMARY_EMBED_DISPATCH_MS,
    ):
        counts[metric_name] += int(agenda_summary_timings.get(metric_name) or 0)


def _run_backfill_loop(
    *,
    catalog_ids: list[int],
    agenda_results: dict[int, dict[str, Any]],
    counts: dict[str, int],
    summary_timeout_seconds: int | None,
    summary_fallback_mode: str,
    progress_callback: Callable[[dict[str, Any]], None] | None,
    progress_every: int,
    generate_summary_callable: Callable[[int], dict[str, Any]],
    summarize_catalog_callable: Callable[..., dict[str, Any]],
) -> None:
    with summary_timeout_override(summary_timeout_seconds):
        for index, cid in enumerate(catalog_ids, start=1):
            if cid in agenda_results:
                result = agenda_results[cid]
            else:
                result = summarize_catalog_callable(
                    cid,
                    summary_fallback_mode=summary_fallback_mode,
                    generate_summary_callable=lambda catalog_id: generate_summary_callable(catalog_id),
                    deterministic_summary_callable=lambda catalog_id: build_deterministic_agenda_summary_payload(
                        catalog_id,
                        reindex_callback=reindex_catalog,
                        embed_callback=lambda target_catalog_id: embed_catalog_task.delay(target_catalog_id),
                    ),
                )
            _record_result_counts(counts, result)
            _emit_progress(
                catalog_ids=catalog_ids,
                index=index,
                catalog_id=cid,
                counts=counts,
                result=result,
                progress_callback=progress_callback,
                progress_every=progress_every,
            )


def _record_result_counts(counts: dict[str, int], result: dict[str, Any]) -> None:
    status = str((result or {}).get("status") or "other")
    counts[status if status in counts else "other"] += 1
    counts["changed_catalogs"] += int(bool((result or {}).get("changed")))
    counts["reindexed"] += int((result or {}).get("reindexed") or 0)
    counts["reindex_failed"] += int((result or {}).get("reindex_failed") or 0)
    counts["embed_enqueued"] += int((result or {}).get("embed_enqueued") or 0)
    counts["embed_dispatch_failed"] += int((result or {}).get("embed_dispatch_failed") or 0)
    completion_mode = str((result or {}).get("completion_mode") or "")
    if completion_mode == "agenda_deterministic":
        counts["agenda_deterministic_complete"] += 1
    elif completion_mode == "llm":
        counts["llm_complete"] += 1
    elif completion_mode == "deterministic_fallback":
        counts["deterministic_fallback_complete"] += 1


def _emit_progress(
    *,
    catalog_ids: list[int],
    index: int,
    catalog_id: int,
    counts: dict[str, int],
    result: dict[str, Any],
    progress_callback: Callable[[dict[str, Any]], None] | None,
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
                "last_status": str((result or {}).get("status") or "other"),
                "completion_mode": str((result or {}).get("completion_mode") or ""),
                "error": str((result or {}).get("error") or ""),
            },
        }
    )

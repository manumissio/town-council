from __future__ import annotations

from typing import Any, Callable

from pipeline.backlog_maintenance import (
    build_deterministic_agenda_summary_payloads,
    build_deterministic_non_agenda_summary_payload,
    summarize_catalog_with_maintenance_mode,
    summary_timeout_override,
)
from pipeline.indexer import reindex_catalog, reindex_catalogs
from pipeline.semantic_tasks import embed_catalog_task
from pipeline.summary_backfill_dispatch import enqueue_embed_catalogs
from pipeline.summary_backfill_logging import log_backfill_counts
from pipeline.summary_backfill_progress import (
    add_agenda_batch_counts,
    emit_summary_progress,
    emit_summary_stage_start,
    finish_empty_summary_backfill,
    initial_summary_backfill_counts,
    record_summary_result_counts,
)
from pipeline.summary_backfill_queries import (
    select_catalog_ids_for_summary_hydration,
    summary_doc_kind_map,
)
from pipeline.task_runtime import task_session


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
    non_agenda_summary_builder: Callable[..., dict[str, Any]] = build_deterministic_non_agenda_summary_payload,
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
    counts = initial_summary_backfill_counts(selected=len(catalog_ids))
    if not catalog_ids:
        finish_empty_summary_backfill(counts, progress_callback)
        return counts

    emit_summary_stage_start(counts, len(catalog_ids), progress_callback)
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
        non_agenda_summary_builder=non_agenda_summary_builder,
        summarize_catalog_callable=summarize_catalog_callable,
    )
    log_backfill_counts(counts)
    if progress_callback:
        progress_callback({"event_type": "stage_finish", "stage": "summary", "counts": counts.copy()})
    return counts


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
    add_agenda_batch_counts(counts, agenda_batch)
    return dict(agenda_batch.get("results") or {})


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
    non_agenda_summary_builder: Callable[..., dict[str, Any]],
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
                    deterministic_summary_callable=lambda catalog_id: non_agenda_summary_builder(
                        catalog_id,
                        reindex_callback=reindex_catalog,
                        embed_callback=lambda target_catalog_id: embed_catalog_task.delay(target_catalog_id),
                    ),
                )
            record_summary_result_counts(counts, result)
            emit_summary_progress(
                catalog_ids=catalog_ids,
                index=index,
                catalog_id=cid,
                counts=counts,
                summary_result=result,
                progress_callback=progress_callback,
                progress_every=progress_every,
            )

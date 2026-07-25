from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from functools import partial
from typing import Any

from pipeline import (
    agenda_segmentation_maintenance,
    agenda_summary_batch,
    agenda_summary_fallback,
    indexer,
    non_agenda_summary_fallback,
    semantic_tasks,
    summary_backfill_queries,
    task_runtime,
    task_summary_generation,
)
from pipeline.local_ai_runtime import LocalAIConfigError
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
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class SummaryBackfillLoopContext:
    catalog_ids: list[int]
    agenda_results: dict[int, dict[str, Any]]
    counts: dict[str, int]
    force: bool
    summary_timeout_seconds: int | None
    summary_fallback_mode: str
    progress_callback: Callable[[dict[str, Any]], None] | None
    progress_every: int


@contextmanager
def _summary_backfill_session() -> Iterator[Session]:
    session = task_runtime.task_session()
    try:
        yield session
    finally:
        session.close()


def run_summary_hydration_backfill(
    force: bool = False,
    limit: int | None = None,
    city: str | None = None,
    *,
    summary_timeout_seconds: int | None = None,
    summary_fallback_mode: str = "none",
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
    progress_every: int = 25,
) -> dict[str, int]:
    """
    Generate summaries once across the current eligible backlog snapshot.
    """
    catalog_ids = _select_catalog_ids(
        limit=limit,
        city=city,
    )
    counts = initial_summary_backfill_counts(selected=len(catalog_ids))
    if not catalog_ids:
        finish_empty_summary_backfill(counts, progress_callback)
        return counts

    emit_summary_stage_start(counts, len(catalog_ids), progress_callback)
    doc_kind_by_catalog_id = _load_doc_kind_map(
        catalog_ids=catalog_ids,
    )
    agenda_results = _run_agenda_batch(
        catalog_ids=catalog_ids,
        doc_kind_by_catalog_id=doc_kind_by_catalog_id,
        counts=counts,
    )
    _run_backfill_loop(
        SummaryBackfillLoopContext(
            catalog_ids=catalog_ids,
            agenda_results=agenda_results,
            counts=counts,
            force=force,
            summary_timeout_seconds=summary_timeout_seconds,
            summary_fallback_mode=summary_fallback_mode,
            progress_callback=progress_callback,
            progress_every=progress_every,
        )
    )
    log_backfill_counts(counts)
    if progress_callback:
        progress_callback({"event_type": "stage_finish", "stage": "summary", "counts": counts.copy()})
    return counts


def _select_catalog_ids(
    *,
    limit: int | None,
    city: str | None,
) -> list[int]:
    db = task_runtime.task_session()
    try:
        return summary_backfill_queries.select_catalog_ids_for_summary_hydration(
            db,
            limit,
            city,
        )
    finally:
        db.close()


def _load_doc_kind_map(
    *,
    catalog_ids: list[int],
) -> dict[int, str]:
    db = task_runtime.task_session()
    try:
        return summary_backfill_queries.summary_doc_kind_map(db, catalog_ids)
    finally:
        db.close()


def _run_agenda_batch(
    *,
    catalog_ids: list[int],
    doc_kind_by_catalog_id: dict[int, str],
    counts: dict[str, int],
) -> dict[int, dict[str, Any]]:
    agenda_catalog_ids = [
        catalog_id for catalog_id in catalog_ids if doc_kind_by_catalog_id.get(catalog_id) == "agenda"
    ]
    if not agenda_catalog_ids:
        return {}
    agenda_batch = agenda_summary_batch.build_deterministic_agenda_summary_payloads(
        agenda_catalog_ids,
        reindex_callback=indexer.reindex_catalogs,
        embed_callback=enqueue_embed_catalogs,
        session_factory=_summary_backfill_session,
    )
    add_agenda_batch_counts(counts, agenda_batch)
    return dict(agenda_batch.get("results") or {})


def _run_backfill_loop(context: SummaryBackfillLoopContext) -> None:
    with agenda_segmentation_maintenance.summary_timeout_override(
        context.summary_timeout_seconds
    ):
        for index, catalog_id in enumerate(context.catalog_ids, start=1):
            if catalog_id in context.agenda_results:
                summary_result = context.agenda_results[catalog_id]
            else:
                summary_result = agenda_summary_fallback.summarize_catalog_with_maintenance_mode(
                    catalog_id,
                    summary_fallback_mode=context.summary_fallback_mode,
                    generate_summary_callable=partial(
                        _generate_catalog_summary,
                        force=context.force,
                    ),
                    deterministic_summary_callable=_build_non_agenda_fallback,
                    capture_summary_fallback_events_factory=(
                        agenda_segmentation_maintenance.capture_summary_fallback_events
                    ),
                    session_factory=_summary_backfill_session,
                )
            record_summary_result_counts(context.counts, summary_result)
            emit_summary_progress(
                catalog_ids=context.catalog_ids,
                index=index,
                catalog_id=catalog_id,
                counts=context.counts,
                summary_result=summary_result,
                progress_callback=context.progress_callback,
                progress_every=context.progress_every,
            )


def _build_non_agenda_fallback(
    catalog_id: int,
    fallback_reason: str = "empty_response",
) -> dict[str, Any]:
    return non_agenda_summary_fallback.build_deterministic_non_agenda_summary_payload(
        catalog_id,
        reindex_callback=indexer.reindex_catalog,
        embed_callback=semantic_tasks.embed_catalog_task.delay,
        session_factory=_summary_backfill_session,
        fallback_reason=fallback_reason,
    )


def _generate_catalog_summary(
    catalog_id: int,
    *,
    force: bool,
) -> dict[str, Any]:
    db: Session = task_runtime.task_session()
    try:
        return task_summary_generation.generate_catalog_summary(
            db,
            catalog_id,
            force=force,
        )
    except LocalAIConfigError as config_error:
        task_runtime.logger.critical(
            "LocalAI misconfiguration catalog_id=%s error=%s",
            catalog_id,
            config_error,
        )
        db.rollback()
        return {"status": "error", "error": str(config_error)}
    except (SQLAlchemyError, RuntimeError, ValueError):
        db.rollback()
        raise
    finally:
        db.close()

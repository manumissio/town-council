from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pipeline import (
    agenda_segmentation_maintenance,
    agenda_summary_batch,
    agenda_summary_fallback,
    summary_backfill_queries,
    task_runtime,
)
from pipeline.summary_backfill_logging import log_backfill_counts
from pipeline.summary_backfill_progress import (
    add_agenda_batch_counts,
    emit_summary_progress,
    emit_summary_stage_start,
    finish_empty_summary_backfill,
    initial_summary_backfill_counts,
    record_summary_result_counts,
)
from pipeline.profiling import append_phase_eligibility, profiling_enabled


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


def run_summary_hydration_workload(
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
    capture_eligibility = profiling_enabled()
    if capture_eligibility:
        append_phase_eligibility(
            phase="summarize",
            boundary="before",
            subject="catalog",
            eligible_ids=catalog_ids,
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


def capture_summary_hydration_after_eligibility(
    counts: dict[str, int],
    *,
    limit: int | None = None,
    city: str | None = None,
) -> None:
    if not profiling_enabled():
        return
    eligible_ids = [] if counts["selected"] == 0 else _select_catalog_ids(limit=limit, city=city)
    append_phase_eligibility(
        phase="summarize",
        boundary="after",
        subject="catalog",
        eligible_ids=eligible_ids,
    )


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
    counts = run_summary_hydration_workload(
        force=force,
        limit=limit,
        city=city,
        summary_timeout_seconds=summary_timeout_seconds,
        summary_fallback_mode=summary_fallback_mode,
        progress_callback=progress_callback,
        progress_every=progress_every,
    )
    capture_summary_hydration_after_eligibility(counts, limit=limit, city=city)
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
                    force=context.force,
                    summary_fallback_mode=context.summary_fallback_mode,
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

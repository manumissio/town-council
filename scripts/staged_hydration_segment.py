from __future__ import annotations

from typing import Any

from scripts.hydration_counts import empty_segment_counts
from scripts.hydration_output import emit_progress


def run_segment_city(
    city: str,
    *,
    limit: int | None = None,
    resume_after_id: int | None = None,
    workers: int | None = None,
    segment_mode: str = "normal",
    agenda_timeout_seconds: int | None = None,
    emit_progress_enabled: bool = False,
    emit_progress_callable=emit_progress,
    chunk_index: int | None = None,
) -> dict[str, Any]:
    from scripts import segment_city_corpus

    selected_catalog_ids = segment_city_corpus._catalog_ids_for_city(city, limit=limit, resume_after_id=resume_after_id)
    if not selected_catalog_ids:
        return _empty_segment_payload(city, resume_after_id)

    catalog_ids = segment_city_corpus._prioritized_catalog_ids(city, selected_catalog_ids)
    timeout_seconds = agenda_timeout_seconds or segment_city_corpus._catalog_timeout_seconds()
    resolved_workers = segment_city_corpus._catalog_worker_count(workers)
    total_catalogs = len(selected_catalog_ids)
    running_counts = empty_segment_counts()
    _emit_segment_start(city, chunk_index, total_catalogs, timeout_seconds, resolved_workers, resume_after_id, emit_progress_enabled, emit_progress_callable)
    _emit_worker_clamp(city, workers, resolved_workers, emit_progress_enabled, emit_progress_callable)

    def _progress(city_name: str, index: int, total: int, catalog_id: int, outcome: str, duration_seconds: float) -> None:
        emit_progress_callable(
            emit_progress_enabled,
            f"[{city_name}] segmentation_catalog_start chunk={chunk_index or 1} index={index}/{total} catalog_id={catalog_id}",
        )
        running_counts[outcome] += 1
        emit_progress_callable(
            emit_progress_enabled,
            "[{city}] segmentation_catalog_finish chunk={chunk} index={index}/{total_catalogs} catalog_id={catalog_id} "
            "outcome={outcome} duration_seconds={duration:.2f} running_counts={counts}".format(
                city=city_name,
                chunk=chunk_index or 1,
                index=index,
                total_catalogs=total,
                catalog_id=catalog_id,
                outcome=outcome,
                duration=duration_seconds,
                counts=running_counts,
            ),
        )

    counts = segment_city_corpus._segment_catalog_batch(
        city,
        catalog_ids,
        timeout_seconds=timeout_seconds,
        workers=resolved_workers,
        segment_mode=segment_mode,
        agenda_timeout_seconds=agenda_timeout_seconds,
        progress_callback=_progress,
    )
    segment_payload = _normalize_segment_payload(city, counts)
    segment_payload["resume_after_id"] = resume_after_id
    segment_payload["last_catalog_id"] = max(selected_catalog_ids)
    return segment_payload


def _empty_segment_payload(city: str, resume_after_id: int | None) -> dict[str, Any]:
    return {
        "city": city,
        "catalog_count": 0,
        **empty_segment_counts(),
        "resume_after_id": resume_after_id,
        "last_catalog_id": resume_after_id,
    }


def _emit_segment_start(
    city: str,
    chunk_index: int | None,
    total_catalogs: int,
    timeout_seconds: int,
    workers: int,
    resume_after_id: int | None,
    emit_progress_enabled: bool,
    emit_progress_callable,
) -> None:
    emit_progress_callable(
        emit_progress_enabled,
        f"[{city}] segmentation_start chunk={chunk_index or 1} catalog_count={total_catalogs} "
        f"timeout_seconds={timeout_seconds} workers={workers} resume_after_id={resume_after_id}",
    )


def _emit_worker_clamp(city: str, requested_workers: int | None, resolved_workers: int, emit_progress_enabled: bool, emit_progress_callable) -> None:
    if requested_workers is not None and resolved_workers != requested_workers:
        emit_progress_callable(
            emit_progress_enabled,
            f"[{city}] segmentation_workers_clamped requested={requested_workers} effective={resolved_workers}",
        )


def _normalize_segment_payload(city: str, counts: dict[str, Any]) -> dict[str, Any]:
    segment_payload: dict[str, Any] = {
        "city": city,
        "catalog_count": int(counts.get("catalog_count", 0)),
    }
    for count_name in empty_segment_counts():
        segment_payload[count_name] = int(counts.get(count_name, 0))
    return segment_payload

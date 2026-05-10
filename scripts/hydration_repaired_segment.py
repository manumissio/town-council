from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from scripts.hydration_counts import ProgressCallback, empty_repaired_segment_counts
from scripts.hydration_output import emit_progress
from scripts.hydration_repaired_selectors import selector_mode


def run_segment_city(
    city: str,
    *,
    limit: int | None,
    resume_after_id: int | None,
    url_substring: str | None,
    emit_progress_enabled: bool,
    progress_every: int,
    select_segment_catalog_ids,
    segment_one_catalog,
    segment_timeout_override,
    capture_agenda_fallback_events,
    catalog_ids: list[int] | None = None,
    workers: int = 1,
    agenda_timeout_seconds: int | None = None,
    segment_mode: str = "normal",
    status_callback: ProgressCallback | None = None,
) -> dict[str, int]:
    selected_catalog_ids = select_segment_catalog_ids(
        city,
        limit=limit,
        resume_after_id=resume_after_id,
        catalog_ids=catalog_ids,
        url_substring=url_substring,
    )
    counts = {"selected": len(selected_catalog_ids), **empty_repaired_segment_counts()}
    _emit_segment_start(city, counts, limit, resume_after_id, url_substring, emit_progress_enabled, status_callback)
    with segment_timeout_override(agenda_timeout_seconds), capture_agenda_fallback_events() as fallback_counts:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(segment_one_catalog, catalog_id, segment_mode=segment_mode): catalog_id
                for catalog_id in selected_catalog_ids
            }
            for index, future in enumerate(as_completed(futures), start=1):
                catalog_id = futures[future]
                segment_result = future.result()
                status = str(segment_result.get("status") or "other")
                _record_segment_result(counts, status, segment_result, fallback_counts)
                _emit_segment_progress(city, index, selected_catalog_ids, catalog_id, status, counts, emit_progress_enabled, progress_every, status_callback)
    emit_progress(emit_progress_enabled, f"[{city}] segment_finish counts={counts}")
    if status_callback:
        status_callback({"event_type": "stage_finish", "stage": "segment", "counts": counts.copy()})
    return counts


def _emit_segment_start(
    city: str,
    counts: dict[str, int],
    limit: int | None,
    resume_after_id: int | None,
    url_substring: str | None,
    emit_progress_enabled: bool,
    status_callback: ProgressCallback | None,
) -> None:
    emit_progress(
        emit_progress_enabled,
        f"[{city}] segment_start selected={counts['selected']} limit={limit} resume_after_id={resume_after_id} "
        f"selector={selector_mode(url_substring)!r}",
    )
    if status_callback:
        status_callback({"event_type": "stage_start", "stage": "segment", "counts": counts.copy(), "detail": {"selector_mode": selector_mode(url_substring)}})


def _record_segment_result(
    counts: dict[str, int],
    status: str,
    segment_result: dict[str, Any],
    fallback_counts: dict[str, int],
) -> None:
    counts[status] = counts.get(status, 0) + 1
    counts["llm_attempted"] += int(segment_result.get("llm_attempted", 0))
    counts["llm_skipped_heuristic_first"] += int(segment_result.get("llm_skipped_heuristic_first", 0))
    counts["heuristic_complete"] += int(segment_result.get("heuristic_complete", 0))
    counts["timeout_fallbacks"] = int(fallback_counts.get("timeout", 0))
    counts["empty_response_fallbacks"] = int(fallback_counts.get("empty_response", 0))
    counts["llm_timeout_then_fallback"] = counts["timeout_fallbacks"]


def _emit_segment_progress(
    city: str,
    index: int,
    catalog_ids: list[int],
    catalog_id: int,
    status: str,
    counts: dict[str, int],
    emit_progress_enabled: bool,
    progress_every: int,
    status_callback: ProgressCallback | None,
) -> None:
    should_emit = index == 1 or index % progress_every == 0 or index == len(catalog_ids)
    if not should_emit:
        return
    emit_progress(
        emit_progress_enabled,
        f"[{city}] segment_progress done={index}/{len(catalog_ids)} last_catalog_id={catalog_id} "
        f"last_status={status} counts={counts}",
    )
    if status_callback:
        status_callback(
            {
                "event_type": "progress",
                "stage": "segment",
                "counts": counts.copy(),
                "last_catalog_id": catalog_id,
                "detail": {"done": index, "total": len(catalog_ids), "last_status": status},
            }
        )

from __future__ import annotations

from typing import Any

from scripts.hydration_counts import ProgressCallback, empty_repaired_summary_counts
from scripts.hydration_output import emit_progress
from scripts.hydration_repaired_selectors import selector_mode


def summarize_one_catalog(
    catalog_id: int,
    *,
    summarize_catalog_with_maintenance_mode,
    build_deterministic_agenda_summary_payload,
    generate_summary_task,
    embed_catalog_task,
    reindex_catalog,
    summary_fallback_mode: str = "none",
) -> dict[str, Any]:
    try:
        return summarize_catalog_with_maintenance_mode(
            catalog_id,
            summary_fallback_mode=summary_fallback_mode,
            generate_summary_callable=lambda target_catalog_id: generate_summary_task.run(target_catalog_id, force=False),
            deterministic_summary_callable=lambda target_catalog_id: build_deterministic_agenda_summary_payload(
                target_catalog_id,
                reindex_callback=reindex_catalog,
                embed_callback=lambda summary_catalog_id: embed_catalog_task.delay(summary_catalog_id),
            ),
        )
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def run_summary_city(
    city: str,
    *,
    limit: int | None,
    resume_after_id: int | None,
    url_substring: str | None,
    emit_progress_enabled: bool,
    progress_every: int,
    select_summary_catalog_ids,
    summarize_one_catalog,
    summary_timeout_override,
    catalog_ids: list[int] | None = None,
    summary_timeout_seconds: int | None = None,
    summary_fallback_mode: str = "none",
    status_callback: ProgressCallback | None = None,
) -> dict[str, int]:
    selected_catalog_ids = select_summary_catalog_ids(
        city,
        limit=limit,
        resume_after_id=resume_after_id,
        catalog_ids=catalog_ids,
        url_substring=url_substring,
    )
    counts = empty_repaired_summary_counts()
    counts["selected"] = len(selected_catalog_ids)
    _emit_summary_start(city, counts, limit, resume_after_id, url_substring, emit_progress_enabled, status_callback)
    with summary_timeout_override(summary_timeout_seconds):
        for index, catalog_id in enumerate(selected_catalog_ids, start=1):
            summary_result = summarize_one_catalog(catalog_id, summary_fallback_mode=summary_fallback_mode)
            status = str(summary_result.get("status") or "other")
            _record_summary_result(counts, status, summary_result)
            _emit_summary_progress(city, index, selected_catalog_ids, catalog_id, status, summary_result, counts, emit_progress_enabled, progress_every, status_callback)
    emit_progress(emit_progress_enabled, f"[{city}] summary_finish counts={counts}")
    if status_callback:
        status_callback({"event_type": "stage_finish", "stage": "summary", "counts": counts.copy()})
    return counts


def _emit_summary_start(
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
        f"[{city}] summary_start selected={counts['selected']} limit={limit} resume_after_id={resume_after_id} "
        f"selector={selector_mode(url_substring)!r}",
    )
    if status_callback:
        status_callback({"event_type": "stage_start", "stage": "summary", "counts": counts.copy(), "detail": {"selector_mode": selector_mode(url_substring)}})


def _record_summary_result(counts: dict[str, int], status: str, summary_result: dict[str, Any]) -> None:
    if status in counts:
        counts[status] += 1
    else:
        counts["other"] += 1
    completion_mode = str(summary_result.get("completion_mode") or "")
    if completion_mode == "agenda_deterministic":
        counts["agenda_deterministic_complete"] += 1
    elif completion_mode == "llm":
        counts["llm_complete"] += 1
    elif completion_mode == "deterministic_fallback":
        counts["deterministic_fallback_complete"] += 1


def _emit_summary_progress(
    city: str,
    index: int,
    catalog_ids: list[int],
    catalog_id: int,
    status: str,
    summary_result: dict[str, Any],
    counts: dict[str, int],
    emit_progress_enabled: bool,
    progress_every: int,
    status_callback: ProgressCallback | None,
) -> None:
    should_emit = index == 1 or index % progress_every == 0 or index == len(catalog_ids)
    if not should_emit:
        return
    extra = f" last_error={summary_result['error']!r}" if "error" in summary_result else ""
    completion_mode = str(summary_result.get("completion_mode") or "")
    if completion_mode:
        extra += f" completion_mode={completion_mode!r}"
    emit_progress(
        emit_progress_enabled,
        f"[{city}] summary_progress done={index}/{len(catalog_ids)} last_catalog_id={catalog_id} "
        f"last_status={status} counts={counts}{extra}",
    )
    if status_callback:
        status_callback(
            {
                "event_type": "progress",
                "stage": "summary",
                "counts": counts.copy(),
                "last_catalog_id": catalog_id,
                "detail": {"done": index, "total": len(catalog_ids), "last_status": status},
            }
        )

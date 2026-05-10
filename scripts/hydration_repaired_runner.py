from __future__ import annotations

import argparse
import json
from typing import Any

from scripts.hydration_counts import rate_per_second
from scripts.hydration_output import emit_stage_timing
from scripts.hydration_repaired_selectors import selector_mode


def run_cli(
    args: argparse.Namespace,
    *,
    maintenance_run_status_cls,
    run_extract_city,
    run_segment_city,
    run_summary_city,
    time_module,
) -> int:
    emit_progress = not args.json
    run_status = _build_run_status(args, maintenance_run_status_cls)
    if emit_progress:
        print(f"[{args.city}] run_status run_id={run_status.run_id} artifact_dir={run_status.paths.run_dir}", flush=True)
    status_callback = _status_callback(run_status)
    started = time_module.perf_counter()
    status = "failed"
    payload: dict[str, Any] | None = None
    failure_message: str | None = None
    try:
        payload = _run_repaired_stages(args, emit_progress, status_callback, run_extract_city, run_segment_city, run_summary_city, time_module)
        status = "completed"
        _record_success(run_status, payload, time_module.perf_counter() - started)
        _emit_success(args, payload)
        return 0
    except Exception as exc:
        failure_message = str(exc)
        raise
    finally:
        if status != "completed":
            _record_failure(run_status, args, payload, failure_message, time_module.perf_counter() - started)


def _run_repaired_stages(
    args: argparse.Namespace,
    emit_progress: bool,
    status_callback,
    run_extract_city,
    run_segment_city,
    run_summary_city,
    time_module,
) -> dict[str, Any]:
    extract_started = time_module.perf_counter()
    extract_counts, extracted_catalog_ids = run_extract_city(
        args.city,
        limit=args.limit,
        resume_after_id=args.resume_after_id,
        url_substring=args.url_substring,
        emit_progress=emit_progress,
        progress_every=args.progress_every,
        workers=args.extract_workers,
        status_callback=status_callback,
    )
    extract_elapsed = time_module.perf_counter() - extract_started
    if emit_progress:
        emit_stage_timing(args.city, "extract", extract_counts, extract_elapsed)
    segment_started = time_module.perf_counter()
    segment_counts = run_segment_city(
        args.city,
        limit=args.limit,
        resume_after_id=args.resume_after_id,
        url_substring=args.url_substring,
        emit_progress=emit_progress,
        progress_every=args.progress_every,
        catalog_ids=extracted_catalog_ids,
        workers=args.segment_workers,
        agenda_timeout_seconds=args.agenda_timeout_seconds,
        segment_mode=args.segment_mode,
        status_callback=status_callback,
    )
    segment_elapsed = time_module.perf_counter() - segment_started
    if emit_progress:
        emit_stage_timing(args.city, "segment", segment_counts, segment_elapsed)
    summary_started = time_module.perf_counter()
    summary_counts = run_summary_city(
        args.city,
        limit=args.limit,
        resume_after_id=args.resume_after_id,
        url_substring=args.url_substring,
        emit_progress=emit_progress,
        progress_every=args.progress_every,
        catalog_ids=extracted_catalog_ids,
        summary_timeout_seconds=args.summary_timeout_seconds,
        summary_fallback_mode=args.summary_fallback_mode,
        status_callback=status_callback,
    )
    summary_elapsed = time_module.perf_counter() - summary_started
    if emit_progress:
        emit_stage_timing(args.city, "summary", summary_counts, summary_elapsed)
    return _build_payload(args, extract_counts, segment_counts, summary_counts, extract_elapsed, segment_elapsed, summary_elapsed)


def _build_run_status(args: argparse.Namespace, maintenance_run_status_cls):
    return maintenance_run_status_cls(
        tool_name="hydrate_repaired_city_catalogs",
        output_dir=args.output_dir,
        run_id=args.run_id,
        metadata={
            "city": args.city,
            "selector_mode": selector_mode(args.url_substring),
            "args": {
                "limit": args.limit,
                "resume_after_id": args.resume_after_id,
                "url_substring": args.url_substring,
                "progress_every": args.progress_every,
                "extract_workers": args.extract_workers,
                "segment_workers": args.segment_workers,
                "segment_mode": args.segment_mode,
                "agenda_timeout_seconds": args.agenda_timeout_seconds,
                "summary_timeout_seconds": args.summary_timeout_seconds,
                "summary_fallback_mode": args.summary_fallback_mode,
                "json": args.json,
            },
        },
    )


def _status_callback(run_status):
    def _callback(event: dict[str, Any]) -> None:
        stage = str(event["stage"])
        counts = dict(event["counts"])
        last_catalog_id = event.get("last_catalog_id")
        detail = dict(event.get("detail") or {})
        progress = _progress_payload(str(event["event_type"]), detail)
        run_status.heartbeat(
            status="running",
            stage=stage,
            counts=counts,
            last_catalog_id=last_catalog_id if isinstance(last_catalog_id, int) else None,
            progress=progress,
        )
        run_status.event(
            event_type=str(event["event_type"]),
            stage=stage,
            counts=counts,
            last_catalog_id=last_catalog_id if isinstance(last_catalog_id, int) else None,
            detail=detail or None,
        )

    return _callback


def _progress_payload(event_type: str, detail: dict[str, Any]) -> dict[str, Any] | None:
    if event_type != "progress":
        return None
    return {key: detail[key] for key in ("done", "total", "last_status") if key in detail}


def _build_payload(
    args: argparse.Namespace,
    extract_counts: dict[str, int],
    segment_counts: dict[str, int],
    summary_counts: dict[str, int],
    extract_elapsed: float,
    segment_elapsed: float,
    summary_elapsed: float,
) -> dict[str, Any]:
    return {
        "city": args.city,
        "selector_mode": selector_mode(args.url_substring),
        "url_substring": args.url_substring,
        "resume_after_id": args.resume_after_id,
        "limit": args.limit,
        "progress_every": args.progress_every,
        "extract_workers": args.extract_workers,
        "segment_workers": args.segment_workers,
        "segment_mode": args.segment_mode,
        "agenda_timeout_seconds": args.agenda_timeout_seconds,
        "summary_timeout_seconds": args.summary_timeout_seconds,
        "summary_fallback_mode": args.summary_fallback_mode,
        "extract": extract_counts,
        "segment": segment_counts,
        "summary": summary_counts,
        "timing": _timing_payload(extract_counts, segment_counts, summary_counts, extract_elapsed, segment_elapsed, summary_elapsed),
    }


def _timing_payload(
    extract_counts: dict[str, int],
    segment_counts: dict[str, int],
    summary_counts: dict[str, int],
    extract_elapsed: float,
    segment_elapsed: float,
    summary_elapsed: float,
) -> dict[str, float]:
    return {
        "extract_seconds": round(extract_elapsed, 4),
        "segment_seconds": round(segment_elapsed, 4),
        "summary_seconds": round(summary_elapsed, 4),
        "extract_rate_per_s": round(rate_per_second(extract_counts.get("updated", 0) + extract_counts.get("cached", 0), extract_elapsed), 4),
        "segment_rate_per_s": round(rate_per_second(segment_counts.get("complete", 0), segment_elapsed), 4),
        "summary_rate_per_s": round(rate_per_second(summary_counts.get("complete", 0), summary_elapsed), 4),
    }


def _record_success(run_status, payload: dict[str, Any], elapsed_seconds: float) -> None:
    run_status.heartbeat(status="completed", stage="complete", counts=payload)
    run_status.event(event_type="completed", stage="complete", counts=payload)
    run_status.result(status="completed", counts=payload, elapsed_seconds=elapsed_seconds)


def _emit_success(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"[{args.city}] hydrate_finish payload={payload}", flush=True)


def _record_failure(run_status, args: argparse.Namespace, payload: dict[str, Any] | None, failure_message: str | None, elapsed_seconds: float) -> None:
    failure_payload = payload or {
        "city": args.city,
        "selector_mode": selector_mode(args.url_substring),
        "url_substring": args.url_substring,
    }
    run_status.heartbeat(status="failed", stage="failed", counts=failure_payload)
    run_status.event(
        event_type="failed",
        stage="failed",
        counts=failure_payload,
        detail={"error": failure_message or "unknown_error"},
    )
    run_status.result(
        status="failed",
        counts=failure_payload,
        elapsed_seconds=elapsed_seconds,
        error=failure_message or "unknown_error",
    )

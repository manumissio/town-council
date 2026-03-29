#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time

from pipeline.maintenance_run_status import MaintenanceRunStatus, validate_run_id
from pipeline.tasks import run_summary_hydration_backfill


def _safe_run_id(value: str) -> str:
    try:
        return validate_run_id(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be a positive integer")
    return parsed


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill summaries for eligible catalogs")
    parser.add_argument("--city")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--run-id", type=_safe_run_id, default=None)
    parser.add_argument("--output-dir", default="experiments/results/maintenance")
    parser.add_argument("--progress-every", type=_positive_int, default=25)
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON only")
    args = parser.parse_args()

    run_status = MaintenanceRunStatus(
        tool_name="backfill_summaries",
        output_dir=args.output_dir,
        run_id=args.run_id,
        metadata={
            "city": args.city,
            "args": {
                "force": args.force,
                "limit": args.limit,
                "progress_every": args.progress_every,
                "json": args.json,
            },
        },
    )
    if not args.json:
        print(
            f"[summary_backfill] run_status run_id={run_status.run_id} artifact_dir={run_status.paths.run_dir}",
            flush=True,
        )

    def _status_callback(event: dict[str, object]) -> None:
        stage = str(event["stage"])
        counts = dict(event["counts"])
        last_catalog_id = event.get("last_catalog_id")
        detail = dict(event.get("detail") or {})
        event_type = str(event["event_type"])
        progress = None
        if event_type == "progress":
            progress = {key: detail[key] for key in ("done", "total", "last_status", "completion_mode") if key in detail and detail[key]}
        run_status.heartbeat(
            status="running",
            stage=stage,
            counts=counts,
            last_catalog_id=last_catalog_id if isinstance(last_catalog_id, int) else None,
            progress=progress,
        )
        run_status.event(
            event_type=event_type,
            stage=stage,
            counts=counts,
            last_catalog_id=last_catalog_id if isinstance(last_catalog_id, int) else None,
            detail=detail or None,
        )

    started = time.perf_counter()
    status = "failed"
    counts: dict[str, int] | None = None
    failure_message: str | None = None
    try:
        counts = run_summary_hydration_backfill(
            force=args.force,
            limit=args.limit,
            city=args.city,
            progress_callback=_status_callback,
            progress_every=max(1, args.progress_every),
        )
        status = "completed"
        run_status.heartbeat(status="completed", stage="complete", counts=counts)
        run_status.event(event_type="completed", stage="complete", counts=counts)
        run_status.result(
            status="completed",
            counts=counts,
            elapsed_seconds=time.perf_counter() - started,
        )
        if args.json:
            print(json.dumps(counts, sort_keys=True))
            return 0

        print("Summary Hydration Backfill")
        print("==========================")
        print(f"run_id: {run_status.run_id}")
        print(f"artifact_dir: {run_status.paths.run_dir}")
        for key, value in counts.items():
            print(f"{key}: {value}")
        return 0
    except Exception as exc:
        failure_message = str(exc)
        raise
    finally:
        if status != "completed":
            failure_payload = {"city": args.city}
            if counts:
                failure_payload.update(counts)
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
                elapsed_seconds=time.perf_counter() - started,
                error=failure_message or "unknown_error",
            )


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Callable

from scripts.operator_profile_artifacts import build_result_payload


def _manifest_package_summary(manifest_package: dict) -> dict[str, Any]:
    return {
        "schema_version": int(manifest_package.get("schema_version") or 0),
        "manifest_name": manifest_package.get("manifest_name"),
        "phase_selected_counts": {key: len(value) for key, value in (manifest_package.get("strata") or {}).items()},
        "expected_phase_coverage": dict(manifest_package.get("expected_phase_coverage") or {}),
    }


def write_run_manifest(
    *,
    write_json: Callable[[Path, dict], None],
    utc_now_iso: Callable[[], str],
    run_dir: Path,
    run_id: str,
    mode: str,
    city: str | None,
    include_batch: bool,
    catalog_ids: list[int],
    provider_counters_before_run: dict[str, float] | None,
    manifest_package: dict | None,
) -> dict[str, Any]:
    run_manifest: dict[str, Any] = {
        "run_id": run_id,
        "mode": mode,
        "started_at": utc_now_iso(),
        "baseline_valid": mode == "baseline",
        "catalog_ids": catalog_ids,
        "catalog_count": len(catalog_ids),
        "city": city,
        "include_batch": include_batch,
        "workload_only": True,
        "profile": {
            key: os.getenv(key)
            for key in (
                "LOCAL_AI_BACKEND",
                "LOCAL_AI_HTTP_API",
                "LOCAL_AI_HTTP_PROFILE",
                "LOCAL_AI_HTTP_MODEL",
                "WORKER_CONCURRENCY",
                "WORKER_POOL",
                "OLLAMA_NUM_PARALLEL",
            )
            if os.getenv(key) is not None
        },
        "provider_counters_before_run": provider_counters_before_run,
    }
    if manifest_package is not None:
        run_manifest["manifest_package"] = _manifest_package_summary(manifest_package)
    write_json(run_dir / "run_manifest.json", run_manifest)
    return run_manifest


def write_result_manifest(
    *,
    write_json: Callable[[Path, dict], None],
    segment_status_from_log: Callable[[Path], dict],
    utc_now_iso: Callable[[], str],
    run_dir: Path,
    run_id: str,
    status: str,
    started_at: str,
    started: float,
    include_batch: bool,
    command_segments: list[dict[str, Any]],
    command_log: Path,
    error_message: str | None,
) -> None:
    write_json(
        run_dir / "result.json",
        build_result_payload(
            run_id=run_id,
            status=status,
            started_at=started_at,
            finished_at=utc_now_iso(),
            elapsed_seconds=time.perf_counter() - started,
            include_batch=include_batch,
            segments=command_segments,
            error_message=error_message,
            quality=segment_status_from_log(command_log),
        ),
    )

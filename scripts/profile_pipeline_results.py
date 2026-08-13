from __future__ import annotations

import hashlib
import time
from pathlib import Path
from typing import Any, Callable

from scripts.operator_profile_artifacts import build_result_payload


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
    profile: dict[str, str],
    source_manifest: str | None,
    source_manifest_bytes: bytes,
    git_commit: str,
    tracked_tree_clean: bool,
) -> dict[str, Any]:
    run_manifest: dict[str, Any] = {
        "run_id": run_id,
        "mode": mode,
        "started_at": utc_now_iso(),
        "baseline_valid": False,
        "baseline_validation_reasons": ["run_incomplete"],
        "baseline_validation_warnings": [],
        "catalog_ids": catalog_ids,
        "catalog_count": len(catalog_ids),
        "city": city,
        "include_batch": include_batch,
        "workload_only": True,
        "profile": profile,
        "source_manifest": source_manifest,
        "source_manifest_name": Path(source_manifest).stem if source_manifest else None,
        "source_manifest_sha256": hashlib.sha256(source_manifest_bytes).hexdigest(),
        "git_commit": git_commit,
        "tracked_tree_clean": tracked_tree_clean,
        "provider_counters_before_run": provider_counters_before_run,
    }
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

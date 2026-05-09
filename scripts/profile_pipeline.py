#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from scripts.collect_soak_metrics import _fetch_worker_metrics_via_docker
from scripts.operator_cli import safe_run_id as _safe_run_id
from scripts.operator_profile_artifacts import load_manifest_catalog_ids as _load_manifest_catalog_ids
from scripts.operator_profile_artifacts import path_for_profile_env
from scripts.operator_profile_artifacts import segment_status_from_log as _segment_status_from_log
from scripts.operator_profile_artifacts import utc_now_iso as _utc_now_iso
from scripts.operator_profile_artifacts import write_catalog_manifest as _write_catalog_manifest
from scripts.operator_profile_artifacts import write_json as _write_json
from scripts.operator_prometheus import parse_metrics as _parse_metrics
from scripts.operator_prometheus import sum_metric as _sum_metric
from scripts.profile_pipeline_runner import ProfilePipelineDeps
from scripts.profile_pipeline_runner import run_profile
from scripts.profile_pipeline_selection import select_triage_catalog_ids as _select_triage_catalog_ids


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = "experiments/results/profiling"
DEFAULT_TRIAGE_LIMIT = 25
TRIAGE_SELECTOR_SERVICE = "worker"
CORE_PROFILE_SERVICE = "worker"
BATCH_PROFILE_SERVICE = "enrichment-worker"


def _path_for_profile_env(path: Path) -> str:
    return path_for_profile_env(path, REPO_ROOT)


def _provider_counters_before_run() -> dict[str, float] | None:
    raw, err = _fetch_worker_metrics_via_docker()
    if err or not raw.strip():
        return None
    rows = _parse_metrics(raw)
    return {
        "provider_requests_total": float(_sum_metric(rows, "tc_provider_requests_total")),
        "provider_timeouts_total": float(_sum_metric(rows, "tc_provider_timeouts_total")),
        "provider_retries_total": float(_sum_metric(rows, "tc_provider_retries_total")),
    }


def _run_command(command: list[str], *, env: dict[str, str], cwd: Path, log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"$ {' '.join(command)}\n")
        handle.flush()
        completed = subprocess.run(
            command,
            cwd=str(cwd),
            env=env,
            text=True,
            stdout=handle,
            stderr=subprocess.STDOUT,
        )
    if completed.returncode != 0:
        raise subprocess.CalledProcessError(completed.returncode, command)


def _run_json_command(command: list[str], *, cwd: Path) -> dict:
    completed = subprocess.run(command, cwd=str(cwd), text=True, capture_output=True)
    if completed.returncode != 0:
        raise subprocess.CalledProcessError(
            completed.returncode,
            command,
            output=completed.stdout,
            stderr=completed.stderr,
        )
    for raw_line in reversed(completed.stdout.splitlines()):
        line = raw_line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    raise RuntimeError(f"expected JSON object in stdout for command: {' '.join(command)}")


def _prepare_manifest_package_via_docker(manifest_rel: str, *, dry_run: bool) -> dict:
    statement = (
        "import json; "
        "from pathlib import Path; "
        "from pipeline.profile_manifest import apply_preconditioning, load_manifest_package; "
        f"manifest_path=Path({manifest_rel!r}); "
        "package=load_manifest_package(manifest_path); "
        "assert package is not None, 'manifest package missing'; "
        f"print(json.dumps(apply_preconditioning(package, dry_run={str(bool(dry_run))}), sort_keys=True))"
    )
    command = [
        "docker",
        "compose",
        "exec",
        "-T",
        "-w",
        "/app",
        TRIAGE_SELECTOR_SERVICE,
        "python",
        "-c",
        statement,
    ]
    return _run_json_command(command, cwd=REPO_ROOT)


def _run_db_migrate_via_docker(*, log_path: Path) -> None:
    command = [
        "docker",
        "compose",
        "exec",
        "-T",
        "-w",
        "/app/pipeline",
        TRIAGE_SELECTOR_SERVICE,
        "python",
        "db_migrate.py",
    ]
    _run_command(command, env=os.environ.copy(), cwd=REPO_ROOT, log_path=log_path)


def _run_backfill_catalog_hashes_via_docker(*, log_path: Path) -> None:
    command = [
        "docker",
        "compose",
        "exec",
        "-T",
        "-w",
        "/app",
        TRIAGE_SELECTOR_SERVICE,
        "python",
        "pipeline/backfill_catalog_hashes.py",
    ]
    _run_command(command, env=os.environ.copy(), cwd=REPO_ROOT, log_path=log_path)


def _select_triage_catalog_ids_via_docker(limit: int, city: str | None) -> dict:
    selector = (
        "import json; "
        "from scripts.profile_pipeline import _select_triage_catalog_ids; "
        f"ids=_select_triage_catalog_ids(limit={int(limit)}, city={city!r}); "
        "print(json.dumps({'catalog_ids': ids, 'catalog_count': len(ids)}))"
    )
    command = [
        "docker",
        "compose",
        "exec",
        "-T",
        TRIAGE_SELECTOR_SERVICE,
        "python",
        "-c",
        selector,
    ]
    return _run_json_command(command, cwd=REPO_ROOT)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Profile the end-to-end Town Council pipeline.")
    parser.add_argument("--mode", choices=("triage", "baseline"), required=True)
    parser.add_argument("--run-id", type=_safe_run_id, default=None)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--manifest", help="Pinned catalog manifest for baseline runs.")
    parser.add_argument("--limit", type=int, default=DEFAULT_TRIAGE_LIMIT)
    parser.add_argument("--city", default=None)
    parser.add_argument("--api-url", default="http://localhost:8000")
    parser.add_argument("--skip-batch", action="store_true")
    parser.add_argument("--dry-run-prepare", action="store_true")
    parser.add_argument("--compare-to", default=None)
    return parser.parse_args(argv)


def _deps() -> ProfilePipelineDeps:
    return ProfilePipelineDeps(
        repo_root=REPO_ROOT,
        core_service=CORE_PROFILE_SERVICE,
        batch_service=BATCH_PROFILE_SERVICE,
        load_manifest_catalog_ids=_load_manifest_catalog_ids,
        path_for_profile_env=_path_for_profile_env,
        provider_counters_before_run=_provider_counters_before_run,
        prepare_manifest_package_via_docker=_prepare_manifest_package_via_docker,
        run_backfill_catalog_hashes_via_docker=_run_backfill_catalog_hashes_via_docker,
        run_command=_run_command,
        run_db_migrate_via_docker=_run_db_migrate_via_docker,
        select_triage_catalog_ids_via_docker=_select_triage_catalog_ids_via_docker,
        segment_status_from_log=_segment_status_from_log,
        subprocess_module=subprocess,
        sys_executable=sys.executable,
        utc_now_iso=_utc_now_iso,
        write_catalog_manifest=_write_catalog_manifest,
        write_json=_write_json,
    )


def main(argv: list[str] | None = None) -> int:
    return run_profile(parse_args(argv), _deps())


if __name__ == "__main__":
    raise SystemExit(main())

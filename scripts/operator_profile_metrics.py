from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib import request

from scripts.operator_numeric import safe_float


def provider_run_deltas_from_manifest(
    manifest: dict[str, Any],
    *,
    provider_requests_total: float,
    provider_timeouts_total: float,
    provider_retries_total: float,
) -> dict[str, float | None]:
    from scripts.operator_profile_metric_deltas import provider_run_deltas_from_manifest as _provider_run_deltas

    return _provider_run_deltas(
        manifest,
        provider_requests_total=provider_requests_total,
        provider_timeouts_total=provider_timeouts_total,
        provider_retries_total=provider_retries_total,
    )


def fetch_text(url: str, timeout: int = 10) -> str:
    with request.urlopen(url, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def docker_exec_python(script: str) -> str:
    from scripts.operator_profile_worker_metrics import docker_exec_python as _docker_exec_python

    return _docker_exec_python(script)


def fetch_worker_metrics_via_docker() -> tuple[str, str | None]:
    from scripts.operator_profile_worker_metrics import fetch_worker_metrics_via_docker as _fetch_worker_metrics

    return _fetch_worker_metrics(exec_python=docker_exec_python)


def hist_quantile(rows: list[dict[str, Any]], base_name: str, labels: dict[str, str], quantile: float) -> float | None:
    buckets: dict[float, float] = {}
    for row in rows:
        if row["name"] != f"{base_name}_bucket":
            continue
        row_labels = row["labels"]
        ok = True
        for key, expected in labels.items():
            if row_labels.get(key) != expected:
                ok = False
                break
        if not ok:
            continue
        le = row_labels.get("le")
        if le is None:
            continue
        if le == "+Inf":
            upper = float("inf")
        else:
            try:
                upper = float(le)
            except (TypeError, ValueError):
                continue
        buckets[upper] = float(row["value"])

    if not buckets:
        return None
    sorted_bounds = sorted(buckets.items(), key=lambda x: x[0])
    total = sorted_bounds[-1][1]
    if total <= 0:
        return 0.0
    target = total * quantile
    prev_bound = 0.0
    prev_count = 0.0
    for bound, count in sorted_bounds:
        if count >= target:
            if count == prev_count:
                return float(bound if bound != float("inf") else prev_bound)
            frac = (target - prev_count) / (count - prev_count)
            if bound == float("inf"):
                return float(prev_bound)
            return float(prev_bound + (bound - prev_bound) * frac)
        prev_bound = bound if bound != float("inf") else prev_bound
        prev_count = count
    return float(prev_bound)


def provider_metrics_state(rows: list[dict[str, Any]], worker_metrics_error: str | None) -> tuple[bool, str]:
    if worker_metrics_error:
        return False, "worker_scrape_failed"
    provider_series_present = any(str(row.get("name", "")).startswith("tc_provider_") for row in rows)
    if provider_series_present:
        return True, "ok"
    return False, "no_provider_series"


def load_json_file(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def load_run_manifest(run_dir: Path) -> dict[str, Any]:
    return load_json_file(run_dir / "run_manifest.json")


def load_tasks_rows(run_dir: Path) -> list[dict[str, Any]]:
    path = run_dir / "tasks.jsonl"
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def task_duration(rows: list[dict[str, Any]], phase: str) -> list[tuple[int | None, float]]:
    out: list[tuple[int | None, float]] = []
    for row in rows:
        if row.get("phase") != phase:
            continue
        try:
            duration = float(row.get("duration_s") or 0.0)
        except (TypeError, ValueError):
            duration = 0.0
        catalog_id = row.get("catalog_id")
        try:
            catalog_value = int(catalog_id)
        except (TypeError, ValueError):
            catalog_value = None
        out.append((catalog_value, duration))
    return out


def slowest_task(rows: list[dict[str, Any]]) -> dict[str, Any]:
    slowest_phase = ""
    slowest_catalog_id = None
    slowest_duration_s = 0.0
    segment_max_s = 0.0
    summary_max_s = 0.0

    for row in rows:
        try:
            duration = float(row.get("duration_s") or 0.0)
        except (TypeError, ValueError):
            duration = 0.0
        phase = str(row.get("phase") or "")
        catalog_id = row.get("catalog_id")
        try:
            catalog_value = int(catalog_id)
        except (TypeError, ValueError):
            catalog_value = None

        if duration >= slowest_duration_s:
            slowest_phase = phase
            slowest_catalog_id = catalog_value
            slowest_duration_s = duration
        if phase == "segment":
            segment_max_s = max(segment_max_s, duration)
        if phase == "summarize":
            summary_max_s = max(summary_max_s, duration)

    return {
        "slowest_phase": slowest_phase or None,
        "slowest_catalog_id": slowest_catalog_id,
        "slowest_duration_s": float(slowest_duration_s),
        "segment_max_s": float(segment_max_s),
        "summary_max_s": float(summary_max_s),
    }


def submission_failure_breakdown(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = {
        "task_submission_failures": 0,
        "task_submission_error_failures": 0,
        "unexpected_non_processing_status_failures": 0,
        "missing_task_id_failures": 0,
        "task_poll_timeouts": 0,
    }
    for row in rows:
        error = str(row.get("error") or "").strip()
        if not error:
            continue
        if error == "task_submission_error":
            counts["task_submission_failures"] += 1
            counts["task_submission_error_failures"] += 1
        elif error.startswith("unexpected_non_processing_status:"):
            counts["task_submission_failures"] += 1
            counts["unexpected_non_processing_status_failures"] += 1
        elif error == "missing_task_id":
            counts["task_submission_failures"] += 1
            counts["missing_task_id_failures"] += 1
        elif error == "task_poll_timeout":
            counts["task_poll_timeouts"] += 1
    return counts

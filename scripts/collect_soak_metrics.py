#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from scripts.operator_prometheus import PROM_LINE as PROM_LINE
from scripts.operator_prometheus import parse_metrics as _parse_metrics
from scripts.operator_prometheus import sum_metric as _sum_metric
from scripts.operator_profile_metrics import fetch_text as _fetch_text
from scripts.operator_profile_metrics import fetch_worker_metrics_via_docker as _fetch_worker_metrics_via_docker
from scripts.operator_profile_metrics import hist_quantile as _hist_quantile
from scripts.operator_profile_metrics import load_run_manifest as _load_run_manifest
from scripts.operator_profile_metrics import load_tasks_rows as _load_tasks_rows
from scripts.operator_profile_metrics import provider_metrics_state as _provider_metrics_state
from scripts.operator_profile_metrics import slowest_task as _slowest_task
from scripts.operator_profile_metrics import submission_failure_breakdown as _submission_failure_breakdown
from scripts.operator_profile_metric_deltas import provider_run_deltas_from_manifest as _provider_run_deltas_from_manifest


def _search_p95_ms(api_url: str) -> float | None:
    samples: list[float] = []
    url = f"{api_url.rstrip('/')}/search?q=zoning&limit=10"
    for _ in range(10):
        t0 = time.perf_counter()
        try:
            _fetch_text(url, timeout=10)
        except Exception:
            return None
        samples.append((time.perf_counter() - t0) * 1000.0)
    if not samples:
        return None
    ordered = sorted(samples)
    idx = max(0, int((0.95 * len(ordered)) + 0.999999) - 1)
    return float(ordered[idx])


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect daily soak metrics snapshots")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output-dir", default="experiments/results/soak")
    parser.add_argument("--api-url", default="http://localhost:8000")
    args = parser.parse_args()

    run_dir = Path(args.output_dir) / args.run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    api_metrics_raw = ""
    try:
        api_metrics_raw = _fetch_text(f"{args.api_url.rstrip('/')}/metrics", timeout=10)
    except Exception:
        api_metrics_raw = ""

    worker_metrics_raw, worker_metrics_error = _fetch_worker_metrics_via_docker()

    (run_dir / "api_metrics.prom").write_text(api_metrics_raw, encoding="utf-8")
    (run_dir / "worker_metrics.prom").write_text(worker_metrics_raw, encoding="utf-8")

    worker_rows = _parse_metrics(worker_metrics_raw)
    provider_metrics_present, provider_metrics_reason = _provider_metrics_state(worker_rows, worker_metrics_error)
    manifest = _load_run_manifest(run_dir)
    task_rows = _load_tasks_rows(run_dir)
    run_hotspots = _slowest_task(task_rows)
    failure_breakdown = _submission_failure_breakdown(task_rows)

    provider_requests_total = _sum_metric(worker_rows, "tc_provider_requests_total")
    provider_timeouts_total = _sum_metric(worker_rows, "tc_provider_timeouts_total")
    provider_retries_total = _sum_metric(worker_rows, "tc_provider_retries_total")
    provider_timeout_rate = (
        float(provider_timeouts_total / provider_requests_total)
        if provider_requests_total > 0
        else None
    )

    ttft_p95_ms = _hist_quantile(worker_rows, "tc_provider_ttft_ms", {}, 0.95)
    ttft_median_ms = _hist_quantile(worker_rows, "tc_provider_ttft_ms", {}, 0.5)
    tps_median = _hist_quantile(worker_rows, "tc_provider_tokens_per_sec", {}, 0.5)

    prompt_tokens_total = _sum_metric(worker_rows, "tc_provider_prompt_tokens_total")
    completion_tokens_total = _sum_metric(worker_rows, "tc_provider_completion_tokens_total")
    run_provider = _provider_run_deltas_from_manifest(
        manifest,
        provider_requests_total=provider_requests_total,
        provider_timeouts_total=provider_timeouts_total,
        provider_retries_total=provider_retries_total,
    )

    day_summary = {}
    day_summary_path = run_dir / "day_summary.json"
    if day_summary_path.exists():
        day_summary = json.loads(day_summary_path.read_text(encoding="utf-8"))

    day_summary.update(
        {
            "run_id": args.run_id,
            "timestamp_epoch_s": int(time.time()),
            "provider_requests_total": provider_requests_total,
            "provider_timeouts_total": provider_timeouts_total,
            "provider_retries_total": provider_retries_total,
            "provider_timeout_rate": provider_timeout_rate,
            "ttft_median_ms": ttft_median_ms,
            "ttft_p95_ms": ttft_p95_ms,
            "tokens_per_sec_median": tps_median,
            "prompt_tokens_total": prompt_tokens_total,
            "completion_tokens_total": completion_tokens_total,
            "search_p95_ms": _search_p95_ms(args.api_url),
            "provider_metrics_present": provider_metrics_present,
            "provider_metrics_reason": provider_metrics_reason,
            "run_manifest_present": bool(manifest),
            "run_profile": manifest.get("profile") if isinstance(manifest.get("profile"), dict) else None,
            "catalog_ids": manifest.get("catalog_ids") if isinstance(manifest.get("catalog_ids"), list) else None,
            "catalog_count": manifest.get("catalog_count"),
            "metrics_sources": {
                "api_metrics_available": bool(api_metrics_raw.strip()),
                "worker_metrics_available": bool(worker_metrics_raw.strip()),
            },
            "worker_metrics_error": worker_metrics_error,
            **run_provider,
            **run_hotspots,
            **failure_breakdown,
        }
    )

    (run_dir / "day_summary.json").write_text(json.dumps(day_summary, indent=2), encoding="utf-8")
    print(f"wrote soak metrics snapshot: {run_dir / 'day_summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

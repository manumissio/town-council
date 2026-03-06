#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import time
from pathlib import Path
from typing import Any
from urllib import request


PROM_LINE = re.compile(r'^(?P<name>[a-zA-Z_:][a-zA-Z0-9_:]*)(?:\{(?P<labels>[^}]*)\})?\s+(?P<value>-?[0-9]+(?:\.[0-9]+)?)$')
WORKER_METRICS_SCRAPE_ATTEMPTS = 2
WORKER_METRICS_BACKOFF_SECONDS = 0.5


def _fetch_text(url: str, timeout: int = 10) -> str:
    with request.urlopen(url, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _docker_exec_python(script: str) -> str:
    cmd = [
        "docker",
        "compose",
        "exec",
        "-T",
        "worker",
        "python",
        "-c",
        script,
    ]
    return subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT, timeout=30)


def _fetch_worker_metrics_via_docker() -> tuple[str, str | None]:
    # Strategy order is intentional: prefer the worker metrics HTTP endpoint first,
    # then fall back to direct process-registry exposition when the endpoint is unavailable.
    strategies = [
        (
            "worker_http",
            (
                "import urllib.request; "
                "print(urllib.request.urlopen('http://localhost:8001/metrics', timeout=10)"
                ".read().decode('utf-8', errors='replace'))"
            ),
        ),
        (
            "worker_registry",
            (
                "from prometheus_client import CollectorRegistry, generate_latest; "
                "from pipeline.metrics import RedisProviderMetricsCollector; "
                "registry = CollectorRegistry(); "
                "registry.register(RedisProviderMetricsCollector()); "
                "print(generate_latest(registry).decode('utf-8', errors='replace'))"
            ),
        ),
    ]
    errors: list[str] = []
    for strategy_name, script in strategies:
        for attempt in range(1, WORKER_METRICS_SCRAPE_ATTEMPTS + 1):
            try:
                raw = _docker_exec_python(script)
                if raw.strip():
                    # HTTP scrape can return generic process metrics without provider
                    # series; in that case continue to the collector fallback path.
                    if strategy_name == "worker_http":
                        provider_sample_present = any(
                            line.startswith("tc_provider_") and not line.startswith("#")
                            for line in raw.splitlines()
                        )
                        if not provider_sample_present:
                            errors.append(f"{strategy_name}[attempt={attempt}] missing_provider_series")
                            continue
                    return raw, None
                errors.append(f"{strategy_name}[attempt={attempt}] empty_output")
            except Exception as exc:
                errors.append(f"{strategy_name}[attempt={attempt}] {exc}")
            if attempt < WORKER_METRICS_SCRAPE_ATTEMPTS:
                time.sleep(WORKER_METRICS_BACKOFF_SECONDS)
    try:
        joined = "; ".join(errors).strip()
        return "", joined or "worker metrics scrape failed"
    except Exception:
        return "", "worker metrics scrape failed"


def _parse_labels(text: str | None) -> dict[str, str]:
    if not text:
        return {}
    out: dict[str, str] = {}
    for part in text.split(","):
        part = part.strip()
        if not part or "=" not in part:
            continue
        key, value = part.split("=", 1)
        out[key.strip()] = value.strip().strip('"')
    return out


def _parse_metrics(raw: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = PROM_LINE.match(line)
        if not m:
            continue
        rows.append(
            {
                "name": m.group("name"),
                "labels": _parse_labels(m.group("labels")),
                "value": float(m.group("value")),
            }
        )
    return rows


def _sum_metric(rows: list[dict[str, Any]], name: str, labels: dict[str, str] | None = None) -> float:
    total = 0.0
    for row in rows:
        if row["name"] != name:
            continue
        if labels:
            ok = True
            for key, expected in labels.items():
                if row["labels"].get(key) != expected:
                    ok = False
                    break
            if not ok:
                continue
        total += float(row["value"])
    return total


def _hist_quantile(rows: list[dict[str, Any]], base_name: str, labels: dict[str, str], quantile: float) -> float | None:
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
            except Exception:
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


def _provider_metrics_state(rows: list[dict[str, Any]], worker_metrics_error: str | None) -> tuple[bool, str]:
    if worker_metrics_error:
        return False, "worker_scrape_failed"
    provider_series_present = any(str(row.get("name", "")).startswith("tc_provider_") for row in rows)
    if provider_series_present:
        return True, "ok"
    return False, "no_provider_series"


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
            "metrics_sources": {
                "api_metrics_available": bool(api_metrics_raw.strip()),
                "worker_metrics_available": bool(worker_metrics_raw.strip()),
            },
            "worker_metrics_error": worker_metrics_error,
        }
    )

    (run_dir / "day_summary.json").write_text(json.dumps(day_summary, indent=2), encoding="utf-8")
    print(f"wrote soak metrics snapshot: {run_dir / 'day_summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from statistics import median


def _safe_float(value):
    try:
        return float(value)
    except Exception:
        return None


def _safe_int(value):
    try:
        return int(value)
    except Exception:
        return 0


def _load_days(root: Path) -> list[dict]:
    rows: list[dict] = []
    for path in root.glob("*/day_summary.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        ts = int(data.get("timestamp_epoch_s") or int(path.stat().st_mtime))
        rows.append(
            {
                "run_id": str(data.get("run_id") or path.parent.name),
                "ts": ts,
                "data": data,
            }
        )
    rows.sort(key=lambda r: r["ts"])
    return rows


def _counter_delta(curr: float | None, prev: float | None) -> float | None:
    if curr is None:
        return None
    if prev is None:
        return curr
    if curr >= prev:
        return curr - prev
    # Counter reset/container restart.
    return curr


def _has_adverse_drift(values: list[float], higher_is_worse: bool, tolerance: float = 0.15) -> bool:
    if len(values) < 4:
        return False
    first = median(values[:2])
    last = median(values[-2:])
    if first == 0:
        return False
    change = (last - first) / first
    if higher_is_worse:
        return change > tolerance
    return change < -tolerance


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate 7-day soak promotion gates")
    parser.add_argument("--input-dir", default="experiments/results/soak")
    parser.add_argument("--window-days", type=int, default=7)
    parser.add_argument("--search-baseline-ms", type=float, default=None)
    args = parser.parse_args()

    root = Path(args.input_dir)
    days = _load_days(root)
    if len(days) < args.window_days:
        raise SystemExit(f"need at least {args.window_days} day summaries, found {len(days)}")
    window = days[-args.window_days:]

    per_day = []
    prev = None
    timeout_rate_days = []
    ttft_days = []
    tps_days = []
    segment_p95_days = []
    summary_p95_days = []
    queue_proxy_days = []
    search_days = []
    failed_day_count = 0
    timeout_storms = 0
    extract_warning_days = 0
    degraded_telemetry_days = 0

    for row in window:
        d = row["data"]
        requests_total = _safe_float(d.get("provider_requests_total"))
        timeouts_total = _safe_float(d.get("provider_timeouts_total"))
        retries_total = _safe_float(d.get("provider_retries_total"))

        req_delta = _counter_delta(
            requests_total,
            None if prev is None else _safe_float(prev["data"].get("provider_requests_total")),
        )
        timeout_delta = _counter_delta(
            timeouts_total,
            None if prev is None else _safe_float(prev["data"].get("provider_timeouts_total")),
        )
        retry_delta = _counter_delta(
            retries_total,
            None if prev is None else _safe_float(prev["data"].get("provider_retries_total")),
        )

        timeout_rate_delta = None
        if req_delta is not None and req_delta > 0 and timeout_delta is not None:
            timeout_rate_delta = timeout_delta / req_delta
            timeout_rate_days.append(timeout_rate_delta)

        gating_failures = _safe_int(d.get("gating_failures"))
        if gating_failures > 0:
            failed_day_count += 1

        extract_failures = _safe_int(d.get("extract_failures"))
        if extract_failures > 0:
            extract_warning_days += 1

        worker_metrics_available = bool((d.get("metrics_sources") or {}).get("worker_metrics_available", False))
        phases_total = _safe_int(d.get("phases_total"))
        requests_total_value = _safe_float(d.get("provider_requests_total")) or 0.0
        telemetry_confidence = "high"
        if (not worker_metrics_available) or (phases_total > 0 and requests_total_value <= 0.0):
            telemetry_confidence = "degraded"
            degraded_telemetry_days += 1

        if (timeout_delta or 0) > 0 and (retry_delta or 0) > 0:
            ratio = (retry_delta or 0) / max(1.0, timeout_delta or 0)
            if ratio >= 3.0:
                timeout_storms += 1

        ttft = _safe_float(d.get("ttft_p95_ms"))
        tps = _safe_float(d.get("tokens_per_sec_median"))
        seg = _safe_float(d.get("segment_p95_s"))
        summ = _safe_float(d.get("summary_p95_s"))
        queue_proxy = _safe_float(d.get("phase_duration_p95_s"))
        search = _safe_float(d.get("search_p95_ms"))

        if ttft is not None:
            ttft_days.append(ttft)
        if tps is not None:
            tps_days.append(tps)
        if seg is not None:
            segment_p95_days.append(seg)
        if summ is not None:
            summary_p95_days.append(summ)
        if queue_proxy is not None:
            queue_proxy_days.append(queue_proxy)
        if search is not None:
            search_days.append(search)

        per_day.append(
            {
                "run_id": row["run_id"],
                "date": datetime.fromtimestamp(row["ts"]).strftime("%Y-%m-%d"),
                "status": d.get("status"),
                "extract_failures": extract_failures,
                "segment_failures": _safe_int(d.get("segment_failures")),
                "summarize_failures": _safe_int(d.get("summarize_failures")),
                "gating_failures": gating_failures,
                "provider_requests_delta": req_delta,
                "provider_timeouts_delta": timeout_delta,
                "provider_retries_delta": retry_delta,
                "provider_timeout_rate_delta": timeout_rate_delta,
                "segment_p95_s": seg,
                "summary_p95_s": summ,
                "phase_duration_p95_s": queue_proxy,
                "ttft_p95_ms": ttft,
                "tokens_per_sec_median": tps,
                "search_p95_ms": search,
                "worker_metrics_available": worker_metrics_available,
                "worker_metrics_error": d.get("worker_metrics_error"),
                "telemetry_confidence": telemetry_confidence,
            }
        )
        prev = row

    gate_provider_timeout = bool(timeout_rate_days) and all(x < 0.01 for x in timeout_rate_days)
    gate_timeout_storms = timeout_storms == 0
    gate_day_failures = failed_day_count == 0

    gate_queue_trend = not _has_adverse_drift(queue_proxy_days, higher_is_worse=True, tolerance=0.20)

    gate_segment_stable = not _has_adverse_drift(segment_p95_days, higher_is_worse=True, tolerance=0.20)
    gate_summary_stable = not _has_adverse_drift(summary_p95_days, higher_is_worse=True, tolerance=0.20)

    gate_search = True
    if args.search_baseline_ms is not None and search_days:
        gate_search = all(((v - args.search_baseline_ms) / args.search_baseline_ms) <= 0.15 for v in search_days)

    gate_telemetry_drift = (
        (not _has_adverse_drift(ttft_days, higher_is_worse=True, tolerance=0.20))
        and (not _has_adverse_drift(tps_days, higher_is_worse=False, tolerance=0.20))
    )

    gates = {
        "provider_timeout_rate_lt_1pct": gate_provider_timeout,
        "timeout_storms_zero": gate_timeout_storms,
        "no_failed_days": gate_day_failures,
        "queue_wait_proxy_no_upward_trend": gate_queue_trend,
        "segment_p95_stable": gate_segment_stable,
        "summary_p95_stable": gate_summary_stable,
        "search_p95_regression_le_15pct": gate_search,
        "ttft_tps_no_persistent_adverse_drift": gate_telemetry_drift,
    }

    overall_pass = all(gates.values())
    out = {
        "window_days": args.window_days,
        "evaluated_runs": [r["run_id"] for r in window],
        "per_day": per_day,
        "gates": gates,
        "overall_pass": overall_pass,
        "extract_warning_days": extract_warning_days,
        "telemetry_confidence": "degraded" if degraded_telemetry_days > 0 else "high",
        "degraded_telemetry_days": degraded_telemetry_days,
        "notes": [
            "Counter-based gates are evaluated using day-over-day deltas.",
            "queue_wait gate uses phase_duration_p95_s proxy unless explicit queue metric is added later.",
            "extract failures are non-gating warnings in this soak phase.",
        ],
    }

    out_json = root / f"soak_eval_{args.window_days}d.json"
    out_md = root / f"soak_eval_{args.window_days}d.md"
    out_json.write_text(json.dumps(out, indent=2), encoding="utf-8")

    lines = [
        f"# Soak Evaluation ({args.window_days} days)",
        "",
        f"overall_pass: {'PASS' if overall_pass else 'FAIL'}",
        f"extract_warning_days: {extract_warning_days}",
        f"telemetry_confidence: {'degraded' if degraded_telemetry_days > 0 else 'high'}",
        f"degraded_telemetry_days: {degraded_telemetry_days}",
        "",
        "## Gates",
    ]
    for k, v in gates.items():
        lines.append(f"- {k}: {'PASS' if v else 'FAIL'}")
    lines.append("")
    lines.append("## Runs")
    for d in per_day:
        lines.append(
            f"- {d['date']} {d['run_id']} status={d['status']} telemetry={d['telemetry_confidence']} extract_failures={d['extract_failures']} gating_failures={d['gating_failures']} timeout_rate_delta={d['provider_timeout_rate_delta']} seg_p95={d['segment_p95_s']} sum_p95={d['summary_p95_s']}"
        )
    lines.append("")
    lines.append("## Notes")
    for n in out["notes"]:
        lines.append(f"- {n}")
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"wrote: {out_json}")
    print(f"wrote: {out_md}")
    print(f"overall_pass={overall_pass}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

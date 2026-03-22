#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from statistics import median

GATE_PASS = "PASS"
GATE_FAIL = "FAIL"
GATE_INCONCLUSIVE = "INCONCLUSIVE"


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


def _run_float(data: dict, key: str) -> float | None:
    value = _safe_float(data.get(key))
    if value is None:
        return None
    return value


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


def _status_from_bool(value: bool) -> str:
    return GATE_PASS if value else GATE_FAIL


def _overall_status(gate_statuses: dict[str, str]) -> str:
    values = list(gate_statuses.values())
    if any(v == GATE_FAIL for v in values):
        return GATE_FAIL
    if any(v == GATE_INCONCLUSIVE for v in values):
        return GATE_INCONCLUSIVE
    return GATE_PASS


def _render_markdown(out: dict) -> str:
    lines = [
        f"# Soak Evaluation ({out['window_days']} days)",
        "",
        f"overall_status: {out['overall_status']}",
        f"overall_pass: {'PASS' if out['overall_pass'] else 'FAIL'}",
        f"extract_warning_days: {out['extract_warning_days']}",
        f"telemetry_confidence: {out['telemetry_confidence']}",
        f"degraded_telemetry_days: {out['degraded_telemetry_days']}",
        f"baseline_valid: {out['baseline_valid']}",
        f"baseline_artifact_days: {out['baseline_artifact_days']}/{out['window_days']}",
        f"evaluated_runs: {', '.join(out['evaluated_runs'])}",
        "",
        "## Gates",
    ]
    for key, value in out["gates"].items():
        status = out["gate_statuses"].get(key, _status_from_bool(value))
        reason = out["gate_reasons"].get(key, "n/a")
        lines.append(f"- {key}: {status} (bool={'PASS' if value else 'FAIL'}, reason={reason})")
    lines.append("")
    lines.append("## Evidence Quality")
    if out["evidence_quality_reasons"]:
        for reason in out["evidence_quality_reasons"]:
            lines.append(f"- {reason}")
    else:
        lines.append("- ok")
    lines.append("")
    lines.append("## Runs")
    for day in out["per_day"]:
        lines.append(
            f"- {day['date']} {day['run_id']} status={day['status']} telemetry={day['telemetry_confidence']} evidence={day['promotion_evidence_source']} extract_failures={day['extract_failures']} gating_failures={day['gating_failures']} timeout_rate_delta={day['provider_timeout_rate_delta']} seg_p95={day['segment_p95_s']} sum_p95={day['summary_p95_s']}"
        )
    lines.append("")
    lines.append("## Notes")
    for note in out["notes"]:
        lines.append(f"- {note}")
    return "\n".join(lines) + "\n"


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
    queue_proxy_capped_used_days = 0
    baseline_artifact_days = 0
    evidence_quality_reasons: list[str] = []

    for row in window:
        d = row["data"]
        requests_total = _safe_float(d.get("provider_requests_total"))
        timeouts_total = _safe_float(d.get("provider_timeouts_total"))
        retries_total = _safe_float(d.get("provider_retries_total"))
        run_requests_delta = _run_float(d, "provider_requests_delta_run")
        run_timeouts_delta = _run_float(d, "provider_timeouts_delta_run")
        run_retries_delta = _run_float(d, "provider_retries_delta_run")

        run_delta_present = (
            run_requests_delta is not None
            and run_timeouts_delta is not None
            and run_retries_delta is not None
        )
        if run_delta_present:
            baseline_artifact_days += 1
            req_delta = run_requests_delta
            timeout_delta = run_timeouts_delta
            retry_delta = run_retries_delta
        else:
            req_delta = None
            timeout_delta = None
            retry_delta = None

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
        queue_proxy = _safe_float(d.get("phase_duration_p95_s_capped"))
        queue_proxy_source = "phase_duration_p95_s_capped"
        if queue_proxy is None:
            queue_proxy = _safe_float(d.get("phase_duration_p95_s"))
            queue_proxy_source = "phase_duration_p95_s"
        else:
            queue_proxy_capped_used_days += 1
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
                "queue_proxy_source": queue_proxy_source,
                "ttft_p95_ms": ttft,
                "tokens_per_sec_median": tps,
                "search_p95_ms": search,
                "worker_metrics_available": worker_metrics_available,
                "worker_metrics_error": d.get("worker_metrics_error"),
                "telemetry_confidence": telemetry_confidence,
                "promotion_evidence_source": "run_delta" if run_delta_present else "legacy_cumulative_only",
            }
        )
        prev = row

    # Run-local deltas make each soak day decision-grade on its own. Legacy summaries
    # only have cumulative counters, which are diagnostic but not promotion-safe.
    if timeout_rate_days and baseline_artifact_days == len(window):
        gate_provider_timeout = all(x < 0.01 for x in timeout_rate_days)
        gate_provider_timeout_status = _status_from_bool(gate_provider_timeout)
        gate_provider_timeout_reason = "ok" if gate_provider_timeout else "timeout_rate_threshold_exceeded"
    else:
        gate_provider_timeout = False
        gate_provider_timeout_status = GATE_INCONCLUSIVE
        gate_provider_timeout_reason = "missing_run_local_provider_deltas"
        evidence_quality_reasons.append("baseline_contaminated")
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

    gate_statuses = {
        "provider_timeout_rate_lt_1pct": gate_provider_timeout_status,
        "timeout_storms_zero": _status_from_bool(gate_timeout_storms),
        "no_failed_days": _status_from_bool(gate_day_failures),
        "queue_wait_proxy_no_upward_trend": _status_from_bool(gate_queue_trend),
        "segment_p95_stable": _status_from_bool(gate_segment_stable),
        "summary_p95_stable": _status_from_bool(gate_summary_stable),
        "search_p95_regression_le_15pct": _status_from_bool(gate_search),
        "ttft_tps_no_persistent_adverse_drift": _status_from_bool(gate_telemetry_drift),
    }
    gate_reasons = {
        "provider_timeout_rate_lt_1pct": gate_provider_timeout_reason,
        "timeout_storms_zero": "ok" if gate_timeout_storms else "retry_timeout_storm_detected",
        "no_failed_days": "ok" if gate_day_failures else "gating_failures_detected",
        "queue_wait_proxy_no_upward_trend": (
            "ok_using_capped_proxy" if gate_queue_trend and queue_proxy_capped_used_days > 0
            else ("ok" if gate_queue_trend else "queue_proxy_upward_drift")
        ),
        "segment_p95_stable": "ok" if gate_segment_stable else "segment_p95_upward_drift",
        "summary_p95_stable": "ok" if gate_summary_stable else "summary_p95_upward_drift",
        "search_p95_regression_le_15pct": "ok" if gate_search else "search_p95_regression_exceeded",
        "ttft_tps_no_persistent_adverse_drift": "ok" if gate_telemetry_drift else "ttft_tps_adverse_drift",
    }

    overall_status = _overall_status(gate_statuses)
    overall_pass = overall_status == GATE_PASS
    if not gates["queue_wait_proxy_no_upward_trend"] or not gates["segment_p95_stable"] or not gates["summary_p95_stable"]:
        evidence_quality_reasons.append("runtime_variability_detected")
    evidence_quality_reasons = sorted(set(evidence_quality_reasons))
    out = {
        "window_days": args.window_days,
        "evaluated_runs": [r["run_id"] for r in window],
        "per_day": per_day,
        "gates": gates,
        "gate_statuses": gate_statuses,
        "gate_reasons": gate_reasons,
        "overall_status": overall_status,
        "overall_pass": overall_pass,
        "extract_warning_days": extract_warning_days,
        "telemetry_confidence": "degraded" if degraded_telemetry_days > 0 else "high",
        "degraded_telemetry_days": degraded_telemetry_days,
        "queue_proxy_capped_used_days": queue_proxy_capped_used_days,
        "baseline_artifact_days": baseline_artifact_days,
        "baseline_valid": baseline_artifact_days == len(window),
        "evidence_quality_reasons": evidence_quality_reasons,
        "notes": [
            "Run-local provider deltas are required for promotion-grade timeout evaluation.",
            "Legacy summaries with cumulative-only provider counters are diagnostic and produce INCONCLUSIVE timeout gates.",
            "queue_wait gate uses phase_duration_p95_s_capped when present, else phase_duration_p95_s proxy.",
            "extract failures are non-gating warnings in this soak phase.",
        ],
    }

    out_json = root / f"soak_eval_{args.window_days}d.json"
    out_md = root / f"soak_eval_{args.window_days}d.md"
    out_json.write_text(json.dumps(out, indent=2), encoding="utf-8")

    out_md.write_text(_render_markdown(out), encoding="utf-8")

    print(f"wrote: {out_json}")
    print(f"wrote: {out_md}")
    print(f"overall_status={overall_status}")
    print(f"overall_pass={overall_pass}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

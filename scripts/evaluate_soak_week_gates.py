from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from scripts.operator_profile_soak_eval import GATE_INCONCLUSIVE
from scripts.operator_profile_soak_eval import GATE_PASS
from scripts.operator_profile_soak_eval import has_adverse_drift
from scripts.operator_profile_soak_eval import load_days
from scripts.operator_profile_soak_eval import overall_status
from scripts.operator_profile_soak_eval import run_float
from scripts.operator_profile_soak_eval import safe_float
from scripts.operator_profile_soak_eval import safe_int
from scripts.operator_profile_soak_eval import status_from_bool


PROVIDER_TIMEOUT_RATE_LIMIT = 0.01
TIMEOUT_RETRY_STORM_RATIO = 3.0
DRIFT_TOLERANCE = 0.20
SEARCH_REGRESSION_TOLERANCE = 0.15


@dataclass(slots=True)
class SoakEvidence:
    per_day: list[dict[str, Any]] = field(default_factory=list)
    timeout_rate_days: list[float] = field(default_factory=list)
    ttft_days: list[float] = field(default_factory=list)
    tps_days: list[float] = field(default_factory=list)
    segment_p95_days: list[float] = field(default_factory=list)
    summary_p95_days: list[float] = field(default_factory=list)
    queue_proxy_days: list[float] = field(default_factory=list)
    search_days: list[float] = field(default_factory=list)
    failed_day_count: int = 0
    timeout_storms: int = 0
    extract_warning_days: int = 0
    degraded_telemetry_days: int = 0
    queue_proxy_capped_used_days: int = 0
    baseline_artifact_days: int = 0
    evidence_quality_reasons: set[str] = field(default_factory=set)


def evaluate_soak_window(root: Path, *, window_days: int, search_baseline_ms: float | None) -> dict[str, Any]:
    days = load_days(root)
    if len(days) < window_days:
        raise SystemExit(f"need at least {window_days} day summaries, found {len(days)}")
    window = days[-window_days:]
    evidence = SoakEvidence()
    for row in window:
        _record_soak_day(evidence, row)
    gate_payload = _gate_payload(evidence, window_days=window_days, search_baseline_ms=search_baseline_ms)
    return _soak_output(window, evidence, gate_payload, window_days=window_days)


def _record_soak_day(evidence: SoakEvidence, row: dict[str, Any]) -> None:
    day = row["data"]
    run_deltas = _provider_run_deltas(day)
    if run_deltas["present"]:
        evidence.baseline_artifact_days += 1
    timeout_rate_delta = _record_provider_timeout_rate(evidence, run_deltas)
    gating_failures = safe_int(day.get("gating_failures"))
    extract_failures = safe_int(day.get("extract_failures"))
    if gating_failures > 0:
        evidence.failed_day_count += 1
    if extract_failures > 0:
        evidence.extract_warning_days += 1
    telemetry_confidence = _record_telemetry_confidence(evidence, day)
    _record_timeout_storm(evidence, run_deltas)
    queue_proxy, queue_proxy_source = _record_runtime_metrics(evidence, day)
    evidence.per_day.append(
        _day_payload(
            row,
            day,
            run_deltas,
            timeout_rate_delta,
            queue_proxy,
            queue_proxy_source,
            telemetry_confidence,
            gating_failures,
            extract_failures,
        )
    )


def _provider_run_deltas(day: dict[str, Any]) -> dict[str, float | bool | None]:
    requests_delta = run_float(day, "provider_requests_delta_run")
    timeouts_delta = run_float(day, "provider_timeouts_delta_run")
    retries_delta = run_float(day, "provider_retries_delta_run")
    present = requests_delta is not None and timeouts_delta is not None and retries_delta is not None
    return {
        "present": present,
        "requests": requests_delta if present else None,
        "timeouts": timeouts_delta if present else None,
        "retries": retries_delta if present else None,
    }


def _record_provider_timeout_rate(evidence: SoakEvidence, run_deltas: dict[str, float | bool | None]) -> float | None:
    requests_delta = run_deltas["requests"]
    timeouts_delta = run_deltas["timeouts"]
    if isinstance(requests_delta, float) and requests_delta > 0 and isinstance(timeouts_delta, float):
        timeout_rate_delta = timeouts_delta / requests_delta
        evidence.timeout_rate_days.append(timeout_rate_delta)
        return timeout_rate_delta
    return None


def _record_telemetry_confidence(evidence: SoakEvidence, day: dict[str, Any]) -> str:
    worker_metrics_available = bool((day.get("metrics_sources") or {}).get("worker_metrics_available", False))
    phases_total = safe_int(day.get("phases_total"))
    requests_total = safe_float(day.get("provider_requests_total")) or 0.0
    if (not worker_metrics_available) or (phases_total > 0 and requests_total <= 0.0):
        evidence.degraded_telemetry_days += 1
        return "degraded"
    return "high"


def _record_timeout_storm(evidence: SoakEvidence, run_deltas: dict[str, float | bool | None]) -> None:
    timeouts_delta = run_deltas["timeouts"] if isinstance(run_deltas["timeouts"], float) else 0.0
    retries_delta = run_deltas["retries"] if isinstance(run_deltas["retries"], float) else 0.0
    if timeouts_delta > 0 and retries_delta > 0 and (retries_delta / max(1.0, timeouts_delta)) >= TIMEOUT_RETRY_STORM_RATIO:
        evidence.timeout_storms += 1


def _record_runtime_metrics(evidence: SoakEvidence, day: dict[str, Any]) -> tuple[float | None, str]:
    _append_if_present(evidence.ttft_days, safe_float(day.get("ttft_p95_ms")))
    _append_if_present(evidence.tps_days, safe_float(day.get("tokens_per_sec_median")))
    _append_if_present(evidence.segment_p95_days, safe_float(day.get("segment_p95_s")))
    _append_if_present(evidence.summary_p95_days, safe_float(day.get("summary_p95_s")))
    _append_if_present(evidence.search_days, safe_float(day.get("search_p95_ms")))
    queue_proxy = safe_float(day.get("phase_duration_p95_s_capped"))
    source = "phase_duration_p95_s_capped"
    if queue_proxy is None:
        queue_proxy = safe_float(day.get("phase_duration_p95_s"))
        source = "phase_duration_p95_s"
    else:
        evidence.queue_proxy_capped_used_days += 1
    _append_if_present(evidence.queue_proxy_days, queue_proxy)
    return queue_proxy, source


def _append_if_present(values: list[float], value: float | None) -> None:
    if value is not None:
        values.append(value)


def _day_payload(
    row: dict[str, Any],
    day: dict[str, Any],
    run_deltas: dict[str, float | bool | None],
    timeout_rate_delta: float | None,
    queue_proxy: float | None,
    queue_proxy_source: str,
    telemetry_confidence: str,
    gating_failures: int,
    extract_failures: int,
) -> dict[str, Any]:
    return {
        "run_id": row["run_id"],
        "date": datetime.fromtimestamp(row["ts"]).strftime("%Y-%m-%d"),
        "status": day.get("status"),
        "extract_failures": extract_failures,
        "segment_failures": safe_int(day.get("segment_failures")),
        "summarize_failures": safe_int(day.get("summarize_failures")),
        "gating_failures": gating_failures,
        "provider_requests_delta": run_deltas["requests"],
        "provider_timeouts_delta": run_deltas["timeouts"],
        "provider_retries_delta": run_deltas["retries"],
        "provider_timeout_rate_delta": timeout_rate_delta,
        "segment_p95_s": safe_float(day.get("segment_p95_s")),
        "summary_p95_s": safe_float(day.get("summary_p95_s")),
        "phase_duration_p95_s": queue_proxy,
        "queue_proxy_source": queue_proxy_source,
        "ttft_p95_ms": safe_float(day.get("ttft_p95_ms")),
        "tokens_per_sec_median": safe_float(day.get("tokens_per_sec_median")),
        "search_p95_ms": safe_float(day.get("search_p95_ms")),
        "worker_metrics_available": bool((day.get("metrics_sources") or {}).get("worker_metrics_available", False)),
        "worker_metrics_error": day.get("worker_metrics_error"),
        "telemetry_confidence": telemetry_confidence,
        "promotion_evidence_source": "run_delta" if run_deltas["present"] else "legacy_cumulative_only",
    }


def _gate_payload(
    evidence: SoakEvidence,
    *,
    window_days: int,
    search_baseline_ms: float | None,
) -> dict[str, dict[str, bool | str]]:
    provider_timeout, provider_status, provider_reason = _provider_timeout_gate(evidence, window_days)
    gates = {
        "provider_timeout_rate_lt_1pct": provider_timeout,
        "timeout_storms_zero": evidence.timeout_storms == 0,
        "no_failed_days": evidence.failed_day_count == 0,
        "queue_wait_proxy_no_upward_trend": not has_adverse_drift(evidence.queue_proxy_days, True, DRIFT_TOLERANCE),
        "segment_p95_stable": not has_adverse_drift(evidence.segment_p95_days, True, DRIFT_TOLERANCE),
        "summary_p95_stable": not has_adverse_drift(evidence.summary_p95_days, True, DRIFT_TOLERANCE),
        "search_p95_regression_le_15pct": _search_gate(evidence.search_days, search_baseline_ms),
        "ttft_tps_no_persistent_adverse_drift": _telemetry_drift_gate(evidence),
    }
    statuses = {key: status_from_bool(value) for key, value in gates.items()}
    statuses["provider_timeout_rate_lt_1pct"] = provider_status
    return {"gates": gates, "gate_statuses": statuses, "gate_reasons": _gate_reasons(gates, provider_reason, evidence)}


def _provider_timeout_gate(evidence: SoakEvidence, window_days: int) -> tuple[bool, str, str]:
    if evidence.timeout_rate_days and evidence.baseline_artifact_days == window_days:
        passed = all(rate < PROVIDER_TIMEOUT_RATE_LIMIT for rate in evidence.timeout_rate_days)
        return passed, status_from_bool(passed), "ok" if passed else "timeout_rate_threshold_exceeded"
    evidence.evidence_quality_reasons.add("baseline_contaminated")
    return False, GATE_INCONCLUSIVE, "missing_run_local_provider_deltas"


def _search_gate(search_days: list[float], baseline_ms: float | None) -> bool:
    if baseline_ms is None or not search_days:
        return True
    return all(((value - baseline_ms) / baseline_ms) <= SEARCH_REGRESSION_TOLERANCE for value in search_days)


def _telemetry_drift_gate(evidence: SoakEvidence) -> bool:
    return (
        not has_adverse_drift(evidence.ttft_days, higher_is_worse=True, tolerance=DRIFT_TOLERANCE)
        and not has_adverse_drift(evidence.tps_days, higher_is_worse=False, tolerance=DRIFT_TOLERANCE)
    )


def _gate_reasons(gates: dict[str, bool], provider_reason: str, evidence: SoakEvidence) -> dict[str, str]:
    return {
        "provider_timeout_rate_lt_1pct": provider_reason,
        "timeout_storms_zero": "ok" if gates["timeout_storms_zero"] else "retry_timeout_storm_detected",
        "no_failed_days": "ok" if gates["no_failed_days"] else "gating_failures_detected",
        "queue_wait_proxy_no_upward_trend": _queue_gate_reason(gates["queue_wait_proxy_no_upward_trend"], evidence),
        "segment_p95_stable": "ok" if gates["segment_p95_stable"] else "segment_p95_upward_drift",
        "summary_p95_stable": "ok" if gates["summary_p95_stable"] else "summary_p95_upward_drift",
        "search_p95_regression_le_15pct": "ok" if gates["search_p95_regression_le_15pct"] else "search_p95_regression_exceeded",
        "ttft_tps_no_persistent_adverse_drift": "ok" if gates["ttft_tps_no_persistent_adverse_drift"] else "ttft_tps_adverse_drift",
    }


def _queue_gate_reason(passed: bool, evidence: SoakEvidence) -> str:
    if not passed:
        return "queue_proxy_upward_drift"
    if evidence.queue_proxy_capped_used_days > 0:
        return "ok_using_capped_proxy"
    return "ok"


def _soak_output(
    window: list[dict[str, Any]],
    evidence: SoakEvidence,
    gate_payload: dict[str, dict[str, bool | str]],
    *,
    window_days: int,
) -> dict[str, Any]:
    gates = gate_payload["gates"]
    if not gates["queue_wait_proxy_no_upward_trend"] or not gates["segment_p95_stable"] or not gates["summary_p95_stable"]:
        evidence.evidence_quality_reasons.add("runtime_variability_detected")
    status = overall_status(gate_payload["gate_statuses"])
    return {
        "window_days": window_days,
        "evaluated_runs": [row["run_id"] for row in window],
        "per_day": evidence.per_day,
        **gate_payload,
        "overall_status": status,
        "overall_pass": status == GATE_PASS,
        "extract_warning_days": evidence.extract_warning_days,
        "telemetry_confidence": "degraded" if evidence.degraded_telemetry_days > 0 else "high",
        "degraded_telemetry_days": evidence.degraded_telemetry_days,
        "queue_proxy_capped_used_days": evidence.queue_proxy_capped_used_days,
        "baseline_artifact_days": evidence.baseline_artifact_days,
        "baseline_valid": evidence.baseline_artifact_days == len(window),
        "evidence_quality_reasons": sorted(evidence.evidence_quality_reasons),
        "notes": [
            "Run-local provider deltas are required for promotion-grade timeout evaluation.",
            "Legacy summaries with cumulative-only provider counters are diagnostic and produce INCONCLUSIVE timeout gates.",
            "queue_wait gate uses phase_duration_p95_s_capped when present, else phase_duration_p95_s proxy.",
            "extract failures are non-gating warnings in this soak phase.",
        ],
    }

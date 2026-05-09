from __future__ import annotations

from typing import Any

from scripts.operator_profile_metrics import safe_float


def _empty_provider_deltas() -> dict[str, float | None]:
    return {
        "provider_requests_delta_run": None,
        "provider_timeouts_delta_run": None,
        "provider_retries_delta_run": None,
        "provider_timeout_rate_run": None,
    }


def provider_run_deltas_from_manifest(
    manifest: dict[str, Any],
    *,
    provider_requests_total: float,
    provider_timeouts_total: float,
    provider_retries_total: float,
) -> dict[str, float | None]:
    baseline = manifest.get("provider_counters_before_run")
    if not isinstance(baseline, dict):
        return _empty_provider_deltas()

    baseline_keys = (
        "provider_requests_total",
        "provider_timeouts_total",
        "provider_retries_total",
    )
    legacy_keys = (
        "tc_provider_requests_total",
        "tc_provider_timeouts_total",
        "tc_provider_retries_total",
    )
    if any(key in baseline for key in legacy_keys):
        return _empty_provider_deltas()
    if any(key not in baseline for key in baseline_keys):
        return _empty_provider_deltas()

    baseline_requests = safe_float(baseline.get("provider_requests_total"))
    baseline_timeouts = safe_float(baseline.get("provider_timeouts_total"))
    baseline_retries = safe_float(baseline.get("provider_retries_total"))
    if baseline_requests is None or baseline_timeouts is None or baseline_retries is None:
        return _empty_provider_deltas()

    requests = max(0.0, float(provider_requests_total - baseline_requests))
    timeouts = max(0.0, float(provider_timeouts_total - baseline_timeouts))
    retries = max(0.0, float(provider_retries_total - baseline_retries))
    timeout_rate = float(timeouts / requests) if requests > 0 else None
    return {
        "provider_requests_delta_run": requests,
        "provider_timeouts_delta_run": timeouts,
        "provider_retries_delta_run": retries,
        "provider_timeout_rate_run": timeout_rate,
    }

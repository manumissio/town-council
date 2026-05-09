from __future__ import annotations

from pathlib import Path
from typing import Any

from scripts.operator_profile_reports import PHASE_DURATION_TOLERANCE_PCT
from scripts.operator_profile_reports import TOTAL_ELAPSED_TOLERANCE_PCT
from scripts.operator_profile_reports import compare_exact_metric as _compare_exact_metric
from scripts.operator_profile_reports import compare_percentage_metric as _compare_percentage_metric
from scripts.operator_profile_reports import compare_timing_metric as _compare_timing_metric
from scripts.pipeline_profile_analysis import _load_expected_baseline
from scripts.pipeline_profile_analysis import _load_json
from scripts.pipeline_profile_analysis import _load_latest_counter_line
from scripts.pipeline_profile_analysis import rank_bottlenecks


PAIRWISE_CONTROLLED_PROFILE_KEYS = (
    "LOCAL_AI_BACKEND",
    "LOCAL_AI_HTTP_PROFILE",
    "WORKER_CONCURRENCY",
    "WORKER_POOL",
    "OLLAMA_NUM_PARALLEL",
)


def _initial_pairwise_result(
    control_summary: dict[str, Any],
    treatment_summary: dict[str, Any],
    control_manifest: dict[str, Any],
    treatment_manifest: dict[str, Any],
    control_day: dict[str, Any],
    treatment_day: dict[str, Any],
) -> dict[str, Any]:
    return {
        "control_run_id": control_summary.get("run_id"),
        "treatment_run_id": treatment_summary.get("run_id"),
        "status": "pass",
        "reason": "matched",
        "comparable": True,
        "checks": [],
        "control_model": (control_manifest.get("profile") or {}).get("LOCAL_AI_HTTP_MODEL"),
        "treatment_model": (treatment_manifest.get("profile") or {}).get("LOCAL_AI_HTTP_MODEL"),
        "provider_counters": {
            "control": {
                "provider_requests_delta_run": control_day.get("provider_requests_delta_run"),
                "provider_timeouts_delta_run": control_day.get("provider_timeouts_delta_run"),
                "provider_retries_delta_run": control_day.get("provider_retries_delta_run"),
            },
            "treatment": {
                "provider_requests_delta_run": treatment_day.get("provider_requests_delta_run"),
                "provider_timeouts_delta_run": treatment_day.get("provider_timeouts_delta_run"),
                "provider_retries_delta_run": treatment_day.get("provider_retries_delta_run"),
            },
        },
    }


def _mark_non_comparable(comparison: dict[str, Any], reason: str) -> dict[str, Any]:
    comparison.update({"status": "non_comparable", "reason": reason, "comparable": False})
    return comparison


def _append_profile_control_checks(
    checks: list[dict[str, Any]],
    control_manifest: dict[str, Any],
    treatment_manifest: dict[str, Any],
) -> None:
    for key in PAIRWISE_CONTROLLED_PROFILE_KEYS:
        checks.append(
            _compare_exact_metric(
                f"profile.{key}",
                (control_manifest.get("profile") or {}).get(key),
                (treatment_manifest.get("profile") or {}).get(key),
            )
        )
    checks.append(_compare_exact_metric("catalog_ids", control_manifest.get("catalog_ids"), treatment_manifest.get("catalog_ids")))


def _append_top_phase_checks(
    checks: list[dict[str, Any]],
    control_summary: dict[str, Any],
    treatment_summary: dict[str, Any],
) -> None:
    control_phases = {str(phase_row.get("phase")): phase_row for phase_row in control_summary.get("all_phases") or []}
    treatment_phases = {str(phase_row.get("phase")): phase_row for phase_row in treatment_summary.get("all_phases") or []}
    for phase in {str(phase_row.get("phase")) for phase_row in control_summary.get("top_bottlenecks") or []}:
        control_phase = control_phases.get(phase)
        treatment_phase = treatment_phases.get(phase)
        if control_phase is None or treatment_phase is None:
            checks.append(
                {
                    "metric": f"phase.{phase}.duration_s",
                    "control": control_phase.get("duration_s") if control_phase else None,
                    "treatment": treatment_phase.get("duration_s") if treatment_phase else None,
                    "status": "fail",
                    "reason": "artifact_missing",
                }
            )
            continue
        checks.append(
            _compare_percentage_metric(
                f"phase.{phase}.duration_s",
                float(control_phase.get("duration_s") or 0.0),
                float(treatment_phase.get("duration_s") or 0.0),
                PHASE_DURATION_TOLERANCE_PCT,
            )
        )


def _finish_comparison(comparison: dict[str, Any], checks: list[dict[str, Any]]) -> dict[str, Any]:
    comparison["checks"] = checks
    failures = [check for check in checks if check.get("status") == "fail"]
    if failures:
        comparison["status"] = "fail"
        comparison["reason"] = str(failures[0].get("reason") or "regression")
        comparison["failed_checks"] = failures
    return comparison


def compare_profile_runs(control_run_dir: Path, treatment_run_dir: Path) -> dict[str, Any]:
    control_summary = rank_bottlenecks(control_run_dir)
    treatment_summary = rank_bottlenecks(treatment_run_dir)
    control_manifest = _load_json(control_run_dir / "run_manifest.json")
    treatment_manifest = _load_json(treatment_run_dir / "run_manifest.json")
    control_day = _load_json(control_run_dir / "day_summary.json")
    treatment_day = _load_json(treatment_run_dir / "day_summary.json")
    comparison = _initial_pairwise_result(
        control_summary,
        treatment_summary,
        control_manifest,
        treatment_manifest,
        control_day,
        treatment_day,
    )
    if not control_summary.get("baseline_valid") or not treatment_summary.get("baseline_valid"):
        return _mark_non_comparable(comparison, "baseline_invalid")
    if str(control_summary.get("confidence") or "").startswith("reduced-confidence"):
        return _mark_non_comparable(comparison, "control_confidence_reduced")
    if str(treatment_summary.get("confidence") or "").startswith("reduced-confidence"):
        return _mark_non_comparable(comparison, "treatment_confidence_reduced")
    checks: list[dict[str, Any]] = [
        _compare_percentage_metric(
            "elapsed_seconds",
            float(control_summary.get("elapsed_seconds") or 0.0),
            float(treatment_summary.get("elapsed_seconds") or 0.0),
            PHASE_DURATION_TOLERANCE_PCT,
        )
    ]
    _append_profile_control_checks(checks, control_manifest, treatment_manifest)
    _append_top_phase_checks(checks, control_summary, treatment_summary)
    return _finish_comparison(comparison, checks)


def _append_expected_phase_checks(
    checks: list[dict[str, Any]],
    summary: dict[str, Any],
    expected: dict[str, Any],
) -> None:
    actual_phases = {str(phase_row.get("phase")): phase_row for phase_row in summary.get("all_phases") or []}
    for phase_entry in expected.get("top_phases") or []:
        phase = str(phase_entry.get("phase") or "")
        actual = actual_phases.get(phase)
        if actual is None:
            checks.append(
                {
                    "metric": f"phase.{phase}",
                    "expected": round(float(phase_entry.get("duration_s") or 0.0), 3),
                    "actual": None,
                    "status": "fail",
                    "reason": "artifact_missing",
                }
            )
            continue
        checks.append(
            _compare_timing_metric(
                f"phase.{phase}.duration_s",
                float(phase_entry.get("duration_s") or 0.0),
                float(actual.get("duration_s") or 0.0),
                PHASE_DURATION_TOLERANCE_PCT,
            )
        )


def _append_expected_counter_checks(
    checks: list[dict[str, Any]],
    run_dir: Path,
    expected: dict[str, Any],
) -> None:
    for counter_name, expected_counter_values in sorted((expected.get("stable_counters") or {}).items()):
        actual_counter_values = _load_latest_counter_line(run_dir, counter_name)
        if not actual_counter_values:
            checks.append(
                {
                    "metric": f"{counter_name}.__present__",
                    "expected": True,
                    "actual": False,
                    "status": "fail",
                    "reason": "artifact_missing",
                }
            )
            continue
        for key, expected_value in sorted((expected_counter_values or {}).items()):
            checks.append(_compare_exact_metric(f"{counter_name}.{key}", expected_value, actual_counter_values.get(key)))


def compare_against_expected_baseline(run_dir: Path, summary: dict[str, Any], expected_path: Path) -> dict[str, Any]:
    expected = _load_expected_baseline(expected_path)
    comparison: dict[str, Any] = {
        "expected_baseline": str(expected_path),
        "manifest_name": expected.get("manifest_name"),
        "status": "pass",
        "reason": "matched",
        "comparable": True,
        "checks": [],
    }
    if not summary.get("baseline_valid"):
        return _mark_non_comparable(comparison, "baseline_invalid")
    if str(summary.get("confidence") or "").startswith("reduced-confidence"):
        return _mark_non_comparable(comparison, "confidence_reduced")
    checks: list[dict[str, Any]] = [
        _compare_timing_metric(
            "elapsed_seconds",
            float(expected["elapsed_seconds"]),
            float(summary.get("elapsed_seconds") or 0.0),
            TOTAL_ELAPSED_TOLERANCE_PCT,
        )
    ]
    _append_expected_phase_checks(checks, summary, expected)
    _append_expected_counter_checks(checks, run_dir, expected)
    return _finish_comparison(comparison, checks)

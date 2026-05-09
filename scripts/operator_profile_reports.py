from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any


TOTAL_ELAPSED_TOLERANCE_PCT = 20.0
PHASE_DURATION_TOLERANCE_PCT = 25.0
AGENDA_SUMMARY_BUNDLE_BUILD_MS = "agenda_summary_bundle_build_ms"
AGENDA_SUMMARY_RENDER_MS = "agenda_summary_render_ms"
AGENDA_SUMMARY_PERSIST_MS = "agenda_summary_persist_ms"
AGENDA_SUMMARY_REINDEX_MS = "agenda_summary_reindex_ms"
AGENDA_SUMMARY_EMBED_DISPATCH_MS = "agenda_summary_embed_dispatch_ms"
AGENDA_SUMMARY_SUBPHASE_KEYS = (
    AGENDA_SUMMARY_BUNDLE_BUILD_MS,
    AGENDA_SUMMARY_RENDER_MS,
    AGENDA_SUMMARY_PERSIST_MS,
    AGENDA_SUMMARY_REINDEX_MS,
    AGENDA_SUMMARY_EMBED_DISPATCH_MS,
)


def load_expected_baseline(path: Path, load_json: Callable[[Path], dict[str, Any]]) -> dict[str, Any]:
    payload = load_json(path)
    if not payload:
        raise ValueError(f"baseline expectation missing or invalid: {path}")
    required = {"manifest_name", "baseline_valid", "elapsed_seconds", "top_phases", "stable_counters"}
    missing = sorted(required.difference(payload))
    if missing:
        raise ValueError(f"baseline expectation missing required keys: {', '.join(missing)}")
    if not isinstance(payload.get("top_phases"), list):
        raise ValueError("baseline expectation top_phases must be a list")
    if not isinstance(payload.get("stable_counters"), dict):
        raise ValueError("baseline expectation stable_counters must be an object")
    return payload


def compare_percentage_metric(name: str, control: float, treatment: float, tolerance_pct: float) -> dict[str, Any]:
    allowed = round(float(control) * (tolerance_pct / 100.0), 3)
    delta = round(float(treatment) - float(control), 3)
    regression_pct = 0.0 if float(control) == 0.0 else round((delta / float(control)) * 100.0, 2)
    passed = float(treatment) <= float(control) + allowed
    return {
        "metric": name,
        "control": round(float(control), 3),
        "treatment": round(float(treatment), 3),
        "delta": delta,
        "regression_pct": regression_pct,
        "tolerance_pct": tolerance_pct,
        "tolerance_abs": allowed,
        "status": "pass" if passed else "fail",
        "reason": "timing_regression" if not passed else "within_tolerance",
    }


def compare_timing_metric(name: str, expected: float, actual: float, tolerance_pct: float) -> dict[str, Any]:
    allowed = round(float(expected) * (tolerance_pct / 100.0), 3)
    delta = round(float(actual) - float(expected), 3)
    passed = float(actual) <= float(expected) + allowed
    return {
        "metric": name,
        "expected": round(float(expected), 3),
        "actual": round(float(actual), 3),
        "delta": delta,
        "tolerance_pct": tolerance_pct,
        "tolerance_abs": allowed,
        "status": "pass" if passed else "fail",
        "reason": "timing_regression" if not passed else "within_tolerance",
    }


def compare_exact_metric(name: str, expected: Any, actual: Any) -> dict[str, Any]:
    passed = actual == expected
    return {
        "metric": name,
        "expected": expected,
        "actual": actual,
        "status": "pass" if passed else "fail",
        "reason": "workload_shape_drift" if not passed else "match",
    }


def render_report(summary: dict[str, Any]) -> str:
    lines = [
        f"# Pipeline Profile: {summary.get('run_id')}",
        "",
        f"- mode: `{summary.get('mode')}`",
        f"- catalog_count: `{summary.get('catalog_count')}`",
        f"- elapsed_seconds: `{summary.get('elapsed_seconds')}`",
        f"- confidence: `{summary.get('confidence')}`",
        "",
        "## Top 3 Bottlenecks",
    ]
    for index, item in enumerate(summary.get("top_bottlenecks") or [], start=1):
        lines.extend(
            [
                f"{index}. `{item['phase']}`",
                f"   - classification: `{item['classification']}`",
                f"   - wall_clock_s: `{item['duration_s']}`",
                f"   - contribution_pct: `{item['contribution_pct']}`",
                f"   - queue_wait_s: `{item['queue_wait_s']}`",
                f"   - task_duration_s: `{item['task_duration_s']}`",
                f"   - occurrence_count: `{item['occurrence_count']}`",
            ]
        )
    summary_timings = summary.get("summarize_subphase_timings_ms") or {}
    if any(int(summary_timings.get(metric_name) or 0) > 0 for metric_name in AGENDA_SUMMARY_SUBPHASE_KEYS):
        lines.extend(
            [
                "",
                "## Summarize Subphase Timings (ms)",
                f"- `{AGENDA_SUMMARY_BUNDLE_BUILD_MS}`: `{int(summary_timings.get(AGENDA_SUMMARY_BUNDLE_BUILD_MS) or 0)}`",
                f"- `{AGENDA_SUMMARY_RENDER_MS}`: `{int(summary_timings.get(AGENDA_SUMMARY_RENDER_MS) or 0)}`",
                f"- `{AGENDA_SUMMARY_PERSIST_MS}`: `{int(summary_timings.get(AGENDA_SUMMARY_PERSIST_MS) or 0)}`",
                f"- `{AGENDA_SUMMARY_REINDEX_MS}`: `{int(summary_timings.get(AGENDA_SUMMARY_REINDEX_MS) or 0)}`",
                f"- `{AGENDA_SUMMARY_EMBED_DISPATCH_MS}`: `{int(summary_timings.get(AGENDA_SUMMARY_EMBED_DISPATCH_MS) or 0)}`",
            ]
        )
    return "\n".join(lines) + "\n"


def render_compare_report(summary: dict[str, Any], comparison: dict[str, Any]) -> str:
    lines = [
        f"# Baseline Compare: {summary.get('run_id')}",
        "",
        f"- expected_baseline: `{comparison.get('expected_baseline')}`",
        f"- status: `{comparison.get('status')}`",
        f"- reason: `{comparison.get('reason')}`",
        f"- comparable: `{comparison.get('comparable')}`",
        "",
        "## Checks",
    ]
    for check in comparison.get("checks") or []:
        lines.append(
            f"- `{check['metric']}`: `{check['status']}` expected=`{check.get('expected')}` actual=`{check.get('actual')}`"
        )
    return "\n".join(lines) + "\n"


def render_pairwise_compare_report(comparison: dict[str, Any]) -> str:
    lines = [
        f"# Pairwise Profile Compare: {comparison.get('treatment_run_id')}",
        "",
        f"- control_run_id: `{comparison.get('control_run_id')}`",
        f"- treatment_run_id: `{comparison.get('treatment_run_id')}`",
        f"- control_model: `{comparison.get('control_model')}`",
        f"- treatment_model: `{comparison.get('treatment_model')}`",
        f"- status: `{comparison.get('status')}`",
        f"- reason: `{comparison.get('reason')}`",
        f"- comparable: `{comparison.get('comparable')}`",
        "",
        "## Checks",
    ]
    for check in comparison.get("checks") or []:
        lines.append(
            f"- `{check['metric']}`: `{check['status']}` control=`{check.get('control', check.get('expected'))}` treatment=`{check.get('treatment', check.get('actual'))}`"
        )
    return "\n".join(lines) + "\n"

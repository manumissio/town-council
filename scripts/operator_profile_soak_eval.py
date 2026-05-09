from __future__ import annotations

import json
from pathlib import Path
from statistics import median


GATE_PASS = "PASS"
GATE_FAIL = "FAIL"
GATE_INCONCLUSIVE = "INCONCLUSIVE"


def safe_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def safe_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def load_days(root: Path) -> list[dict]:
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


def run_float(data: dict, key: str) -> float | None:
    value = safe_float(data.get(key))
    if value is None:
        return None
    return value


def counter_delta(curr: float | None, prev: float | None) -> float | None:
    if curr is None:
        return None
    if prev is None:
        return curr
    if curr >= prev:
        return curr - prev
    # Counter reset/container restart.
    return curr


def has_adverse_drift(values: list[float], higher_is_worse: bool, tolerance: float = 0.15) -> bool:
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


def status_from_bool(value: bool) -> str:
    return GATE_PASS if value else GATE_FAIL


def overall_status(gate_statuses: dict[str, str]) -> str:
    values = list(gate_statuses.values())
    if any(v == GATE_FAIL for v in values):
        return GATE_FAIL
    if any(v == GATE_INCONCLUSIVE for v in values):
        return GATE_INCONCLUSIVE
    return GATE_PASS


def render_markdown(out: dict) -> str:
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
        status = out["gate_statuses"].get(key, status_from_bool(value))
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

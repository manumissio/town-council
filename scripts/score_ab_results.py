#!/usr/bin/env python3
import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from statistics import median

DEFAULT_GATES = {
    "section_compliance_improvement_pp": 5.0,
    "fallback_increase_pp_max": 1.0,
    "grounding_drop_pp_max": 1.0,
    "manual_review_median_improvement_min": 0.5,
    "summary_p95_increase_pct_max": 25.0,
    "segment_p95_increase_pct_max": 25.0,
    "failure_rate_increase_pp_max": 1.0,
    "queue_wait_p95_minutes_max": 10.0,
    "search_p95_regression_pct_max": 15.0,
}


def _to_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    return text in {"1", "true", "yes", "y"}


def _to_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return float(default)


def _p95(values):
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = max(0, int(math.ceil(0.95 * len(ordered))) - 1)
    return float(ordered[idx])


def aggregate_arm(rows):
    total = len(rows)
    if total == 0:
        return {
            "n": 0,
            "section_compliance_rate": 0.0,
            "fallback_rate": 0.0,
            "grounding_rate": 0.0,
            "failure_rate": 0.0,
            "summary_p95_s": 0.0,
            "segment_p95_s": 0.0,
            "partial_disclosure_rate": 0.0,
        }

    section = sum(1 for r in rows if _to_bool(r.get("section_compliance_pass"))) / total
    fallback = sum(1 for r in rows if _to_bool(r.get("fallback_used"))) / total
    grounding = sum(1 for r in rows if _to_bool(r.get("grounding_pass"))) / total
    failed = sum(1 for r in rows if _to_bool(r.get("task_failed"))) / total
    partial = sum(1 for r in rows if _to_bool(r.get("partial_coverage_disclosed"))) / total

    summary_p95 = _p95([_to_float(r.get("summary_duration_s")) for r in rows])
    segment_p95 = _p95([_to_float(r.get("segment_duration_s")) for r in rows])

    return {
        "n": total,
        "section_compliance_rate": section,
        "fallback_rate": fallback,
        "grounding_rate": grounding,
        "failure_rate": failed,
        "summary_p95_s": summary_p95,
        "segment_p95_s": segment_p95,
        "partial_disclosure_rate": partial,
    }


def compare_arms(control, treatment, gates=None):
    gates = gates or DEFAULT_GATES

    def pct(v):
        return float(v) * 100.0

    deltas = {
        "section_compliance_pp": pct(treatment["section_compliance_rate"] - control["section_compliance_rate"]),
        "fallback_pp": pct(treatment["fallback_rate"] - control["fallback_rate"]),
        "grounding_pp": pct(treatment["grounding_rate"] - control["grounding_rate"]),
        "failure_rate_pp": pct(treatment["failure_rate"] - control["failure_rate"]),
        "summary_p95_pct": ((treatment["summary_p95_s"] - control["summary_p95_s"]) / control["summary_p95_s"] * 100.0) if control["summary_p95_s"] else 0.0,
        "segment_p95_pct": ((treatment["segment_p95_s"] - control["segment_p95_s"]) / control["segment_p95_s"] * 100.0) if control["segment_p95_s"] else 0.0,
    }

    checks = {
        "section_compliance": deltas["section_compliance_pp"] >= gates["section_compliance_improvement_pp"],
        "fallback": deltas["fallback_pp"] <= gates["fallback_increase_pp_max"],
        "grounding": deltas["grounding_pp"] >= -gates["grounding_drop_pp_max"],
        "summary_p95": deltas["summary_p95_pct"] <= gates["summary_p95_increase_pct_max"],
        "segment_p95": deltas["segment_p95_pct"] <= gates["segment_p95_increase_pct_max"],
        "failure_rate": deltas["failure_rate_pp"] <= gates["failure_rate_increase_pp_max"],
    }

    return {
        "deltas": deltas,
        "checks": checks,
        "all_pass": all(checks.values()),
    }


def _load_rows(path: Path):
    if path.suffix.lower() == ".json":
        return json.loads(path.read_text(encoding="utf-8"))

    rows = []
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def _resolve_run_file(base: Path, run_id: str) -> Path:
    run_dir = base / run_id
    json_path = run_dir / "ab_rows.json"
    csv_path = run_dir / "ab_rows.csv"
    if json_path.exists():
        return json_path
    if csv_path.exists():
        return csv_path
    raise FileNotFoundError(f"missing ab rows for run {run_id}: expected {json_path} or {csv_path}")


def _compute_manual_review_delta(blind_csv: str, key_csv: str) -> float | None:
    blind = {}
    with Path(blind_csv).open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            sid = row.get("sample_id", "").strip()
            if sid:
                blind[sid] = row

    key = {}
    with Path(key_csv).open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            sid = row.get("sample_id", "").strip()
            if sid:
                key[sid] = row

    deltas = []
    for sid, mapping in key.items():
        row = blind.get(sid)
        if not row:
            continue
        try:
            a_score = float(row.get("usefulness_score_a_1_5") or "")
            b_score = float(row.get("usefulness_score_b_1_5") or "")
        except Exception:
            continue

        arm_a = (mapping.get("option_a_arm") or "").strip().upper()
        arm_b = (mapping.get("option_b_arm") or "").strip().upper()
        scores = {}
        if arm_a in {"A", "B"}:
            scores[arm_a] = a_score
        if arm_b in {"A", "B"}:
            scores[arm_b] = b_score
        if "A" in scores and "B" in scores:
            deltas.append(scores["B"] - scores["A"])

    if not deltas:
        return None
    return float(median(deltas))


def _render_report(control, treatment, comparison, run_ids):
    lines = []
    lines.append("# A/B Report v1")
    lines.append("")
    lines.append(f"Runs: {', '.join(run_ids)}")
    lines.append("")
    lines.append("## Arm Metrics")
    lines.append("")
    lines.append("| Metric | Control (A) | Treatment (B) |")
    lines.append("|---|---:|---:|")
    rows = [
        ("N", control["n"], treatment["n"]),
        ("Section compliance %", control["section_compliance_rate"] * 100, treatment["section_compliance_rate"] * 100),
        ("Fallback used %", control["fallback_rate"] * 100, treatment["fallback_rate"] * 100),
        ("Grounding pass %", control["grounding_rate"] * 100, treatment["grounding_rate"] * 100),
        ("Failure rate %", control["failure_rate"] * 100, treatment["failure_rate"] * 100),
        ("Summary p95 (s)", control["summary_p95_s"], treatment["summary_p95_s"]),
        ("Segment p95 (s)", control["segment_p95_s"], treatment["segment_p95_s"]),
    ]
    for name, a, b in rows:
        lines.append(f"| {name} | {a:.2f} | {b:.2f} |" if isinstance(a, float) or isinstance(b, float) else f"| {name} | {a} | {b} |")

    lines.append("")
    lines.append("## Gate Evaluation")
    lines.append("")
    for key, passed in comparison["checks"].items():
        lines.append(f"- {key}: {'PASS' if passed else 'FAIL'}")
    for key, passed in comparison.get("extra_checks", {}).items():
        lines.append(f"- {key}: {'PASS' if passed else 'FAIL'}")
    lines.append(f"- overall: {'PASS' if comparison['all_pass'] else 'FAIL'}")
    lines.append("")
    lines.append("## Deltas (B - A)")
    lines.append("")
    for key, value in comparison["deltas"].items():
        lines.append(f"- {key}: {value:.2f}")
    if comparison.get("manual_review_median_delta") is not None:
        lines.append(f"- manual_review_median_delta: {comparison['manual_review_median_delta']:.2f}")

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Score A/B runs and evaluate balanced gates")
    parser.add_argument("--runs", required=True, help="Comma-separated run IDs")
    parser.add_argument("--results-root", default="experiments/results")
    parser.add_argument("--queue-wait-p95-minutes", type=float, default=None)
    parser.add_argument("--search-p95-regression-pct", type=float, default=None)
    parser.add_argument("--manual-review-csv", default=None)
    parser.add_argument("--manual-review-key-csv", default=None)
    args = parser.parse_args()

    run_ids = [r.strip() for r in args.runs.split(",") if r.strip()]
    if not run_ids:
        raise SystemExit("--runs is empty")

    root = Path(args.results_root)
    all_rows = []
    for run_id in run_ids:
        path = _resolve_run_file(root, run_id)
        all_rows.extend(_load_rows(path))

    by_arm = defaultdict(list)
    for row in all_rows:
        arm = str(row.get("arm") or "").strip().upper()
        if arm in {"A", "B"}:
            by_arm[arm].append(row)

    if not by_arm["A"] or not by_arm["B"]:
        raise SystemExit("Need rows for both arms A and B")

    control = aggregate_arm(by_arm["A"])
    treatment = aggregate_arm(by_arm["B"])
    comparison = compare_arms(control, treatment, DEFAULT_GATES)

    extra_checks = {}
    queue_val = args.queue_wait_p95_minutes
    extra_checks["queue_wait_p95"] = (queue_val is not None) and (queue_val <= DEFAULT_GATES["queue_wait_p95_minutes_max"])

    search_reg = args.search_p95_regression_pct
    extra_checks["search_p95_regression"] = (search_reg is not None) and (search_reg <= DEFAULT_GATES["search_p95_regression_pct_max"])

    manual_delta = None
    if args.manual_review_csv and args.manual_review_key_csv:
        manual_delta = _compute_manual_review_delta(args.manual_review_csv, args.manual_review_key_csv)
    extra_checks["manual_review_median"] = (
        manual_delta is not None and manual_delta >= DEFAULT_GATES["manual_review_median_improvement_min"]
    )

    comparison["extra_checks"] = extra_checks
    comparison["manual_review_median_delta"] = manual_delta
    comparison["all_pass"] = comparison["all_pass"] and all(extra_checks.values())

    out = {
        "runs": run_ids,
        "control": control,
        "treatment": treatment,
        "comparison": comparison,
        "inputs": {
            "queue_wait_p95_minutes": queue_val,
            "search_p95_regression_pct": search_reg,
            "manual_review_csv": args.manual_review_csv,
            "manual_review_key_csv": args.manual_review_key_csv,
        },
    }

    report_dir = root
    report_dir.mkdir(parents=True, exist_ok=True)
    stamp = "_".join(run_ids)
    json_path = report_dir / f"ab_score_{stamp}.json"
    md_path = report_dir / "ab_report_v1.md"

    json_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    md_path.write_text(_render_report(control, treatment, comparison, run_ids), encoding="utf-8")

    print(f"wrote score json: {json_path}")
    print(f"wrote report: {md_path}")
    print(f"overall_pass={comparison['all_pass']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

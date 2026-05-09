#!/usr/bin/env python3
import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from statistics import median

from scripts.operator_profile_ab import DEFAULT_GATES
from scripts.operator_profile_ab import aggregate_arm
from scripts.operator_profile_ab import arm_metadata as _arm_metadata
from scripts.operator_profile_ab import compare_arms
from scripts.operator_profile_ab import render_report as _render_report


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


def _load_run_config(base: Path, run_id: str) -> dict:
    path = base / run_id / "run_config.json"
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


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
    run_configs = []
    for run_id in run_ids:
        path = _resolve_run_file(root, run_id)
        all_rows.extend(_load_rows(path))
        run_configs.append(_load_run_config(root, run_id))

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
    arm_metadata = _arm_metadata(all_rows, run_configs)

    out = {
        "runs": run_ids,
        "arm_metadata": arm_metadata,
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
    md_path.write_text(_render_report(control, treatment, comparison, run_ids, arm_metadata), encoding="utf-8")

    print(f"wrote score json: {json_path}")
    print(f"wrote report: {md_path}")
    print(f"overall_pass={comparison['all_pass']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

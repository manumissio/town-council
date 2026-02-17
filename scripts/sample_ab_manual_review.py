#!/usr/bin/env python3
import argparse
import csv
import json
import random
from pathlib import Path


def _load_rows(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Create blinded manual-review sample for A/B summaries")
    parser.add_argument("--runs", required=True, help="Comma-separated run IDs")
    parser.add_argument("--results-root", default="experiments/results")
    parser.add_argument("--sample-size", type=int, default=20)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    run_ids = [r.strip() for r in args.runs.split(",") if r.strip()]
    root = Path(args.results_root)

    by_cid_arm = {}
    for run_id in run_ids:
        rows_path = root / run_id / "ab_rows.json"
        if not rows_path.exists():
            continue
        for row in _load_rows(rows_path):
            cid = int(row.get("catalog_id") or 0)
            arm = str(row.get("arm") or "").strip().upper()
            summary_text = (row.get("summary_text") or "").strip()
            if cid <= 0 or arm not in {"A", "B"} or not summary_text:
                continue
            by_cid_arm.setdefault(cid, {})[arm] = row

    paired = []
    for cid, arms in by_cid_arm.items():
        if "A" in arms and "B" in arms:
            paired.append((cid, arms["A"], arms["B"]))

    if not paired:
        raise SystemExit("No paired A/B summaries found. Run collect_ab_results.py first for both arms.")

    rng = random.Random(args.seed)
    rng.shuffle(paired)
    selected = paired[: min(args.sample_size, len(paired))]

    out_dir = root
    blind_path = out_dir / "manual_review_blind_v1.csv"
    key_path = out_dir / "manual_review_key_v1.csv"

    with blind_path.open("w", encoding="utf-8", newline="") as f_blind, key_path.open("w", encoding="utf-8", newline="") as f_key:
        w_blind = csv.writer(f_blind)
        w_key = csv.writer(f_key)

        w_blind.writerow([
            "sample_id",
            "catalog_id",
            "doc_kind",
            "option_a_summary",
            "option_b_summary",
            "reviewer_choice",
            "usefulness_score_a_1_5",
            "usefulness_score_b_1_5",
            "notes",
        ])
        w_key.writerow(["sample_id", "catalog_id", "option_a_arm", "option_b_arm"])

        for idx, (cid, a_row, b_row) in enumerate(selected, start=1):
            sample_id = f"S{idx:03d}"
            if rng.random() < 0.5:
                option_a, option_b = a_row, b_row
                option_a_arm, option_b_arm = "A", "B"
            else:
                option_a, option_b = b_row, a_row
                option_a_arm, option_b_arm = "B", "A"

            doc_kind = option_a.get("doc_kind") or option_b.get("doc_kind") or "unknown"

            w_blind.writerow(
                [
                    sample_id,
                    cid,
                    doc_kind,
                    option_a.get("summary_text", ""),
                    option_b.get("summary_text", ""),
                    "",
                    "",
                    "",
                    "",
                ]
            )
            w_key.writerow([sample_id, cid, option_a_arm, option_b_arm])

    print(f"wrote blind sheet: {blind_path}")
    print(f"wrote key sheet: {key_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

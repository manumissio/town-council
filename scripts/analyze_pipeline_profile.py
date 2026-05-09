#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.operator_profile_reports import render_compare_report
from scripts.operator_profile_reports import render_pairwise_compare_report
from scripts.operator_profile_reports import render_report
from scripts.pipeline_profile_analysis import rank_bottlenecks
from scripts.pipeline_profile_compare import compare_against_expected_baseline
from scripts.pipeline_profile_compare import compare_profile_runs


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze pipeline profiling artifacts and rank bottlenecks.")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output-dir", default="experiments/results/profiling")
    parser.add_argument("--compare-to", default=None)
    parser.add_argument("--compare-run", default=None)
    return parser.parse_args(argv)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _run_dir(output_dir: str, run_id: str) -> Path:
    output_root = Path(output_dir)
    return output_root / run_id if output_root.name != run_id else output_root


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    run_dir = _run_dir(args.output_dir, args.run_id)
    if args.compare_to and args.compare_run:
        raise SystemExit("--compare-to and --compare-run are mutually exclusive")

    summary = rank_bottlenecks(run_dir)
    _write_json(run_dir / "summary.json", summary)
    (run_dir / "top_bottlenecks.md").write_text(render_report(summary), encoding="utf-8")
    payload: dict[str, Any] = {"run_id": args.run_id, "summary": str(run_dir / "summary.json")}

    if args.compare_to:
        comparison = compare_against_expected_baseline(run_dir, summary, Path(args.compare_to))
        _write_json(run_dir / "baseline_compare.json", comparison)
        (run_dir / "baseline_compare.md").write_text(render_compare_report(summary, comparison), encoding="utf-8")
        payload["baseline_compare"] = str(run_dir / "baseline_compare.json")
        print(json.dumps(payload, indent=2))
        return 0 if comparison.get("status") == "pass" else 1

    if args.compare_run:
        comparison = compare_profile_runs(_run_dir(args.output_dir, args.compare_run), run_dir)
        _write_json(run_dir / "pairwise_compare.json", comparison)
        (run_dir / "pairwise_compare.md").write_text(render_pairwise_compare_report(comparison), encoding="utf-8")
        payload["pairwise_compare"] = str(run_dir / "pairwise_compare.json")
        print(json.dumps(payload, indent=2))
        return 0 if comparison.get("status") == "pass" else 1

    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

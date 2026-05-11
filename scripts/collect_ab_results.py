#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.collect_ab_results_rows import REQUIRED_SECTIONS
from scripts.collect_ab_results_rows import _detect_fallback
from scripts.collect_ab_results_rows import _detect_partial_coverage
from scripts.collect_ab_results_rows import _provider_metric_from_phase_row
from scripts.collect_ab_results_rows import _section_compliance
from scripts.collect_ab_results_rows import _summary_text_from_sources
from scripts.collect_ab_results_rows import _to_float
from scripts.collect_ab_results_rows import _to_int
from scripts.collect_ab_results_rows import collect_ab_rows
from scripts.collect_ab_results_rows import load_task_phase_rows
from scripts.collect_ab_results_rows import write_ab_outputs


def _load_run_config(run_dir: Path) -> dict[str, Any]:
    path = run_dir / "run_config.json"
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _emit_output_summary(*, row_count: int, csv_path: Path, json_path: Path) -> None:
    print(f"wrote {row_count} rows to {csv_path} and {json_path}")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Collect A/B run results into CSV/JSON artifacts")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--results-root", default="experiments/results")
    return parser


def main() -> int:
    args = _parser().parse_args()
    run_dir = Path(args.results_root) / args.run_id
    tasks_path = run_dir / "tasks.jsonl"
    if not tasks_path.exists():
        raise SystemExit(f"missing tasks file: {tasks_path}")
    by_catalog_phase, arm = load_task_phase_rows(tasks_path)
    rows = collect_ab_rows(
        run_id=args.run_id,
        arm=arm,
        by_catalog_phase=by_catalog_phase,
        run_config=_load_run_config(run_dir),
    )
    csv_path, json_path = write_ab_outputs(run_dir, rows)
    _emit_output_summary(row_count=len(rows), csv_path=csv_path, json_path=json_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

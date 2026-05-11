#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.evaluate_soak_week_gates import evaluate_soak_window
from scripts.operator_profile_soak_eval import GATE_FAIL
from scripts.operator_profile_soak_eval import GATE_INCONCLUSIVE
from scripts.operator_profile_soak_eval import GATE_PASS
from scripts.operator_profile_soak_eval import counter_delta as _counter_delta
from scripts.operator_profile_soak_eval import has_adverse_drift as _has_adverse_drift
from scripts.operator_profile_soak_eval import overall_status as _overall_status
from scripts.operator_profile_soak_eval import render_markdown as _render_markdown
from scripts.operator_profile_soak_eval import run_float as _run_float
from scripts.operator_profile_soak_eval import safe_int as _safe_int
from scripts.operator_profile_soak_eval import status_from_bool as _status_from_bool


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate 7-day soak promotion gates")
    parser.add_argument("--input-dir", default="experiments/results/soak")
    parser.add_argument("--window-days", type=int, default=7)
    parser.add_argument("--search-baseline-ms", type=float, default=None)
    return parser


def main() -> int:
    args = _parser().parse_args()
    root = Path(args.input_dir)
    output = evaluate_soak_window(root, window_days=args.window_days, search_baseline_ms=args.search_baseline_ms)
    json_path = root / f"soak_eval_{args.window_days}d.json"
    markdown_path = root / f"soak_eval_{args.window_days}d.md"
    json_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    markdown_path.write_text(_render_markdown(output), encoding="utf-8")

    print(f"wrote: {json_path}")
    print(f"wrote: {markdown_path}")
    print(f"overall_status={output['overall_status']}")
    print(f"overall_pass={output['overall_pass']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

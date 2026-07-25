#!/usr/bin/env python3
from __future__ import annotations

import argparse

from scripts.operator_cli import nonnegative_int as _nonnegative_int
from scripts.operator_cli import positive_int as _positive_int
from scripts.staged_hydration_runner import run_cli


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run staged city hydration: segment -> summarize -> diagnose")
    parser.add_argument("--city", action="append", dest="cities")
    parser.add_argument("--limit", type=_positive_int, default=None, help="Backward-compatible alias for --summary-limit")
    parser.add_argument("--segment-limit", type=_positive_int, default=None)
    parser.add_argument("--summary-limit", type=_positive_int, default=None)
    parser.add_argument("--segment-workers", type=_positive_int, default=None)
    parser.add_argument("--segment-mode", choices=("normal", "maintenance"), default="normal")
    parser.add_argument("--agenda-timeout-seconds", type=_positive_int, default=None, dest="agenda_timeout_seconds")
    parser.add_argument("--summary-timeout-seconds", type=_positive_int, default=None, dest="summary_timeout_seconds")
    parser.add_argument("--summary-fallback-mode", choices=("none", "deterministic"), default="none")
    parser.add_argument("--resume-after-id", type=_nonnegative_int, default=None, dest="resume_after_id")
    parser.add_argument("--max-chunks", type=_positive_int, default=None)
    parser.add_argument("--repeat-until-idle", action="store_true", help="Repeat bounded staged runs until no segmentation or summary work remains")
    parser.add_argument("--sleep-seconds", type=_nonnegative_int, default=2, help="Pause between repeated staged runs")
    parser.add_argument("--force", action="store_true", help="Force summary regeneration for selected cities")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON only")
    return parser


def main() -> int:
    return run_cli(_build_parser().parse_args())


if __name__ == "__main__":
    raise SystemExit(main())

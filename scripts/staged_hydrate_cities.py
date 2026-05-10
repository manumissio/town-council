#!/usr/bin/env python3
from __future__ import annotations

import argparse
import time
from typing import Any

from pipeline.city_scope import ordered_hydration_cities
from pipeline.db_session import db_session
from pipeline.summary_hydration_diagnostics import build_summary_hydration_snapshot
from pipeline.tasks import run_summary_hydration_backfill
from scripts.hydration_counts import empty_staged_summary_counts, merge_counts
from scripts.hydration_output import emit_progress
from scripts.operator_cli import nonnegative_int as _nonnegative_int
from scripts.operator_cli import positive_int as _positive_int
from scripts.staged_hydration_runner import hydration_delta, run_cli, run_once, snapshot_dict
from scripts.staged_hydration_segment import run_segment_city


def _emit_progress(enabled: bool, message: str) -> None:
    return emit_progress(enabled, message)


def _empty_summary_counts() -> dict[str, int]:
    return empty_staged_summary_counts()


def _merge_counts(base: dict[str, int], addition: dict[str, int]) -> dict[str, int]:
    return merge_counts(base, addition)


def _run_segment_city(
    city: str,
    *,
    limit: int | None = None,
    resume_after_id: int | None = None,
    workers: int | None = None,
    segment_mode: str = "normal",
    agenda_timeout_seconds: int | None = None,
    emit_progress: bool = False,
    chunk_index: int | None = None,
) -> dict[str, Any]:
    return run_segment_city(
        city,
        limit=limit,
        resume_after_id=resume_after_id,
        workers=workers,
        segment_mode=segment_mode,
        agenda_timeout_seconds=agenda_timeout_seconds,
        emit_progress_enabled=emit_progress,
        emit_progress_callable=_emit_progress,
        chunk_index=chunk_index,
    )


def _snapshot_dict(city: str) -> dict[str, Any]:
    return snapshot_dict(db_session, build_summary_hydration_snapshot, city)


def _delta(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    return hydration_delta(before, after)


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


def _run_once(args: argparse.Namespace) -> dict[str, Any]:
    return run_once(
        args,
        ordered_hydration_cities=ordered_hydration_cities,
        snapshot_callable=_snapshot_dict,
        segment_callable=_run_segment_city,
        summary_backfill_callable=run_summary_hydration_backfill,
        emit_progress_callable=_emit_progress,
        empty_summary_counts_callable=_empty_summary_counts,
        merge_counts_callable=_merge_counts,
        delta_callable=_delta,
    )


def main() -> int:
    return run_cli(_build_parser().parse_args(), run_once_callable=_run_once, time_module=time, emit_progress_callable=_emit_progress)


if __name__ == "__main__":
    raise SystemExit(main())

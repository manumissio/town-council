from __future__ import annotations

import argparse
import time
from typing import Any

from pipeline import summary_backfill_runner
from pipeline.city_scope import ordered_hydration_cities
from pipeline.db_session import db_session
from pipeline.summary_hydration_diagnostics import build_summary_hydration_snapshot
from scripts.hydration_counts import empty_segment_counts, empty_staged_summary_counts, merge_counts
from scripts.hydration_output import emit_progress
from scripts.staged_hydration_output import emit_before_snapshot, emit_chunk_finish, emit_city_finish, emit_final_output
from scripts.staged_hydration_segment import run_segment_city


def snapshot_dict(city: str) -> dict[str, Any]:
    with db_session() as session:
        return build_summary_hydration_snapshot(session, city=city).to_dict()


def hydration_delta(before_snapshot: dict[str, Any], after_snapshot: dict[str, Any]) -> dict[str, Any]:
    count_names = [
        "catalogs_with_summary",
        "missing_summary_total",
        "agenda_missing_summary_total",
        "agenda_missing_summary_with_items",
        "agenda_missing_summary_without_items",
        "non_agenda_missing_summary_total",
    ]
    delta: dict[str, Any] = {
        count_name: int(after_snapshot[count_name]) - int(before_snapshot[count_name]) for count_name in count_names
    }
    before_statuses = before_snapshot.get("agenda_unresolved_segmentation_status_counts") or {}
    after_statuses = after_snapshot.get("agenda_unresolved_segmentation_status_counts") or {}
    delta["agenda_unresolved_segmentation_status_counts"] = {
        status: int(after_statuses.get(status, 0)) - int(before_statuses.get(status, 0))
        for status in sorted(set(before_statuses) | set(after_statuses))
    }
    return delta


def run_once(args: argparse.Namespace) -> dict[str, Any]:
    cities = args.cities or ordered_hydration_cities()
    summary_limit = args.summary_limit if args.summary_limit is not None else args.limit
    human_progress = not args.json
    results: list[dict[str, Any]] = []
    for city in cities:
        results.append(_run_city(args, city, summary_limit, human_progress))
    any_work_done = any(
        int(city_result["segmentation"]["catalog_count"]) > 0 or int(city_result["summary"]["selected"]) > 0
        for city_result in results
    )
    return {"cities": results, "any_work_done": any_work_done}


def run_cli(args: argparse.Namespace) -> int:
    human_progress = not args.json
    all_runs: list[dict[str, Any]] = []
    run_index = 0
    while True:
        run_index += 1
        _emit_loop_start(args, run_index, human_progress)
        run_payload = run_once(args)
        all_runs.append(run_payload)
        if _should_stop(args, run_payload, run_index, human_progress):
            break
        if args.sleep_seconds > 0:
            emit_progress(human_progress, f"[loop] sleeping seconds={args.sleep_seconds}")
            time.sleep(args.sleep_seconds)
    emit_final_output(args, all_runs)
    return 0


def _run_city(
    args: argparse.Namespace,
    city: str,
    summary_limit: int | None,
    human_progress: bool,
) -> dict[str, Any]:
    emit_progress(human_progress, f"[{city}] city_start")
    before_snapshot = snapshot_dict(city)
    emit_before_snapshot(city, before_snapshot, human_progress)
    chunks, segmentation_total, summary_total, current_snapshot = _run_city_chunks(
        args,
        city,
        summary_limit,
        human_progress,
        before_snapshot,
    )
    delta = hydration_delta(before_snapshot, current_snapshot)
    emit_city_finish(city, current_snapshot, delta, human_progress)
    return {
        "city": city,
        "before": before_snapshot,
        "chunks": chunks,
        "segmentation": segmentation_total,
        "summary": summary_total,
        "after": current_snapshot,
        "delta": delta,
    }


def _run_city_chunks(
    args: argparse.Namespace,
    city: str,
    summary_limit: int | None,
    human_progress: bool,
    current_snapshot: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, int], dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    segmentation_total: dict[str, Any] = {"city": city, "catalog_count": 0, **empty_segment_counts()}
    summary_total = empty_staged_summary_counts()
    current_resume_after_id = args.resume_after_id
    chunk_index = 0
    ran_summary_only_chunk = False
    while True:
        if args.max_chunks is not None and chunk_index >= args.max_chunks:
            break
        chunk_index += 1
        segmentation = _run_segment_chunk(args, city, current_resume_after_id, human_progress, chunk_index)
        summary = _run_summary_chunk(
            args,
            city,
            summary_limit,
            human_progress,
            chunk_index,
            current_snapshot,
            ran_summary_only_chunk,
            segmentation,
        )
        after_snapshot = snapshot_dict(city)
        chunk = _build_chunk(chunk_index, current_resume_after_id, segmentation, summary, current_snapshot, after_snapshot)
        chunks.append(chunk)
        segmentation_total = _merge_segment_totals(city, segmentation_total, segmentation)
        summary_total = merge_counts(summary_total, summary)
        emit_chunk_finish(city, chunk_index, after_snapshot, segmentation, chunk["delta"], human_progress)
        current_snapshot = after_snapshot
        if segmentation["catalog_count"] > 0:
            current_resume_after_id = segmentation["last_catalog_id"]
            continue
        ran_summary_only_chunk = ran_summary_only_chunk or bool(summary["selected"] > 0)
        break
    return chunks, segmentation_total, summary_total, current_snapshot


def _run_segment_chunk(
    args: argparse.Namespace,
    city: str,
    resume_after_id: int | None,
    human_progress: bool,
    chunk_index: int,
) -> dict[str, Any]:
    return run_segment_city(
        city,
        limit=args.segment_limit,
        resume_after_id=resume_after_id,
        workers=args.segment_workers,
        segment_mode=args.segment_mode,
        agenda_timeout_seconds=args.agenda_timeout_seconds,
        emit_progress_enabled=human_progress,
        chunk_index=chunk_index,
    )


def _run_summary_chunk(
    args: argparse.Namespace,
    city: str,
    summary_limit: int | None,
    human_progress: bool,
    chunk_index: int,
    current_snapshot: dict[str, Any],
    ran_summary_only_chunk: bool,
    segmentation: dict[str, Any],
) -> dict[str, int]:
    should_run_summary = segmentation["catalog_count"] > 0 or (
        not ran_summary_only_chunk and current_snapshot["missing_summary_total"] > 0
    )
    if not should_run_summary:
        return empty_staged_summary_counts()
    emit_progress(human_progress, f"[{city}] summary_start chunk={chunk_index} limit={summary_limit}")
    summary = summary_backfill_runner.run_summary_hydration_backfill(
        force=args.force,
        limit=summary_limit,
        city=city,
        summary_timeout_seconds=args.summary_timeout_seconds,
        summary_fallback_mode=args.summary_fallback_mode,
    )
    emit_progress(human_progress, f"[{city}] summary_finish chunk={chunk_index} results={summary}")
    return summary


def _build_chunk(
    chunk_index: int,
    resume_after_id: int | None,
    segmentation: dict[str, Any],
    summary: dict[str, int],
    before_snapshot: dict[str, Any],
    after_snapshot: dict[str, Any],
) -> dict[str, Any]:
    return {
        "chunk_index": chunk_index,
        "resume_after_id": resume_after_id,
        "segmentation": segmentation,
        "summary": summary,
        "after": after_snapshot,
        "delta": hydration_delta(before_snapshot, after_snapshot),
    }


def _merge_segment_totals(city: str, base_counts: dict[str, Any], segment_counts: dict[str, Any]) -> dict[str, Any]:
    merged_counts: dict[str, Any] = {"city": city}
    merged_counts["catalog_count"] = int(base_counts["catalog_count"]) + int(segment_counts["catalog_count"])
    for count_name in empty_segment_counts():
        merged_counts[count_name] = int(base_counts[count_name]) + int(segment_counts[count_name])
    return merged_counts


def _emit_loop_start(args: argparse.Namespace, run_index: int, human_progress: bool) -> None:
    if args.repeat_until_idle:
        emit_progress(
            human_progress,
            f"[loop] run_start run={run_index} max_chunks={args.max_chunks} sleep_seconds={args.sleep_seconds}",
        )


def _should_stop(
    args: argparse.Namespace,
    run_payload: dict[str, Any],
    run_index: int,
    human_progress: bool,
) -> bool:
    if not args.repeat_until_idle:
        return True
    if not run_payload["any_work_done"]:
        emit_progress(human_progress, f"[loop] idle_stop run={run_index}")
        return True
    return False

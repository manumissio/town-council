#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from typing import Any

from pipeline.city_scope import ordered_hydration_cities
from pipeline.db_session import db_session
from pipeline.summary_hydration_diagnostics import build_summary_hydration_snapshot
from pipeline.tasks import run_summary_hydration_backfill


def _emit_progress(enabled: bool, message: str) -> None:
    if enabled:
        print(message, flush=True)


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be a positive integer")
    return parsed


def _nonnegative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("value must be a non-negative integer")
    return parsed


def _empty_summary_counts() -> dict[str, int]:
    return {
        "selected": 0,
        "complete": 0,
        "cached": 0,
        "stale": 0,
        "blocked_low_signal": 0,
        "blocked_ungrounded": 0,
        "not_generated_yet": 0,
        "error": 0,
        "other": 0,
        "llm_complete": 0,
        "deterministic_fallback_complete": 0,
    }


def _merge_counts(base: dict[str, int], addition: dict[str, int]) -> dict[str, int]:
    merged = dict(base)
    for key, value in addition.items():
        merged[key] = int(merged.get(key, 0)) + int(value)
    return merged


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
    from scripts import segment_city_corpus

    selected_catalog_ids = segment_city_corpus._catalog_ids_for_city(city, limit=limit, resume_after_id=resume_after_id)
    if not selected_catalog_ids:
        return {
            "city": city,
            "catalog_count": 0,
            "complete": 0,
            "empty": 0,
            "failed": 0,
            "timed_out": 0,
            "other": 0,
            "timeout_fallbacks": 0,
            "empty_response_fallbacks": 0,
            "llm_attempted": 0,
            "llm_skipped_heuristic_first": 0,
            "heuristic_complete": 0,
            "llm_timeout_then_fallback": 0,
            "resume_after_id": resume_after_id,
            "last_catalog_id": resume_after_id,
        }

    catalog_ids = segment_city_corpus._prioritized_catalog_ids(city, selected_catalog_ids)
    timeout_seconds = agenda_timeout_seconds or segment_city_corpus._catalog_timeout_seconds()
    resolved_workers = segment_city_corpus._catalog_worker_count(workers)
    running_counts = {
        "complete": 0,
        "empty": 0,
        "failed": 0,
        "timed_out": 0,
        "other": 0,
        "timeout_fallbacks": 0,
        "empty_response_fallbacks": 0,
        "llm_attempted": 0,
        "llm_skipped_heuristic_first": 0,
        "heuristic_complete": 0,
        "llm_timeout_then_fallback": 0,
    }
    total_catalogs = len(selected_catalog_ids)
    _emit_progress(
        emit_progress,
        f"[{city}] segmentation_start chunk={chunk_index or 1} catalog_count={total_catalogs} "
        f"timeout_seconds={timeout_seconds} workers={resolved_workers} resume_after_id={resume_after_id}",
    )
    if workers is not None and resolved_workers != workers:
        _emit_progress(
            emit_progress,
            f"[{city}] segmentation_workers_clamped requested={workers} effective={resolved_workers}",
        )

    def _progress(city_name: str, index: int, total: int, catalog_id: int, outcome: str, duration_seconds: float) -> None:
        _emit_progress(
            emit_progress,
            f"[{city_name}] segmentation_catalog_start chunk={chunk_index or 1} index={index}/{total} catalog_id={catalog_id}",
        )
        running_counts[outcome] += 1
        _emit_progress(
            emit_progress,
            "[{city}] segmentation_catalog_finish chunk={chunk} index={index}/{total_catalogs} catalog_id={catalog_id} "
            "outcome={outcome} duration_seconds={duration:.2f} running_counts={counts}".format(
                city=city_name,
                chunk=chunk_index or 1,
                index=index,
                total_catalogs=total,
                catalog_id=catalog_id,
                outcome=outcome,
                duration=duration_seconds,
                counts=running_counts,
            ),
        )

    counts = segment_city_corpus._segment_catalog_batch(
        city,
        catalog_ids,
        timeout_seconds=timeout_seconds,
        workers=resolved_workers,
        segment_mode=segment_mode,
        agenda_timeout_seconds=agenda_timeout_seconds,
        progress_callback=_progress,
    )
    counts = {
        "city": city,
        "catalog_count": int(counts.get("catalog_count", 0)),
        "complete": int(counts.get("complete", 0)),
        "empty": int(counts.get("empty", 0)),
        "failed": int(counts.get("failed", 0)),
        "timed_out": int(counts.get("timed_out", 0)),
        "other": int(counts.get("other", 0)),
        "timeout_fallbacks": int(counts.get("timeout_fallbacks", 0)),
        "empty_response_fallbacks": int(counts.get("empty_response_fallbacks", 0)),
        "llm_attempted": int(counts.get("llm_attempted", 0)),
        "llm_skipped_heuristic_first": int(counts.get("llm_skipped_heuristic_first", 0)),
        "heuristic_complete": int(counts.get("heuristic_complete", 0)),
        "llm_timeout_then_fallback": int(counts.get("llm_timeout_then_fallback", 0)),
    }
    counts["resume_after_id"] = resume_after_id
    counts["last_catalog_id"] = max(selected_catalog_ids)
    return counts


def _snapshot_dict(city: str) -> dict[str, Any]:
    with db_session() as session:
        return build_summary_hydration_snapshot(session, city=city).to_dict()


def _delta(before: dict[str, Any], after: dict[str, Any]) -> dict[str, int]:
    keys = [
        "catalogs_with_summary",
        "missing_summary_total",
        "agenda_missing_summary_total",
        "agenda_missing_summary_with_items",
        "agenda_missing_summary_without_items",
        "non_agenda_missing_summary_total",
    ]
    delta = {key: int(after[key]) - int(before[key]) for key in keys}
    before_statuses = before.get("agenda_unresolved_segmentation_status_counts") or {}
    after_statuses = after.get("agenda_unresolved_segmentation_status_counts") or {}
    all_statuses = sorted(set(before_statuses) | set(after_statuses))
    delta["agenda_unresolved_segmentation_status_counts"] = {
        status: int(after_statuses.get(status, 0)) - int(before_statuses.get(status, 0))
        for status in all_statuses
    }
    return delta


def main() -> int:
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
    parser.add_argument("--force", action="store_true", help="Force summary regeneration for selected cities")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON only")
    args = parser.parse_args()

    cities = args.cities or ordered_hydration_cities()
    summary_limit = args.summary_limit if args.summary_limit is not None else args.limit
    human_progress = not args.json
    results: list[dict[str, Any]] = []
    for city in cities:
        _emit_progress(human_progress, f"[{city}] city_start")
        before = _snapshot_dict(city)
        _emit_progress(
            human_progress,
            "[{city}] before_snapshot missing_summary_total={missing} catalogs_with_summary={summaries} "
            "agenda_missing_without_items={agenda_without_items} agenda_missing_with_items={agenda_with_items} "
            "non_agenda_missing={non_agenda_missing}".format(
                city=city,
                missing=before["missing_summary_total"],
                summaries=before["catalogs_with_summary"],
                agenda_without_items=before["agenda_missing_summary_without_items"],
                agenda_with_items=before["agenda_missing_summary_with_items"],
                non_agenda_missing=before["non_agenda_missing_summary_total"],
            ),
        )
        chunks: list[dict[str, Any]] = []
        segmentation_total = {
            "city": city,
            "catalog_count": 0,
            "complete": 0,
            "empty": 0,
            "failed": 0,
            "timed_out": 0,
            "other": 0,
            "timeout_fallbacks": 0,
            "empty_response_fallbacks": 0,
            "llm_attempted": 0,
            "llm_skipped_heuristic_first": 0,
            "heuristic_complete": 0,
            "llm_timeout_then_fallback": 0,
        }
        summary_total = _empty_summary_counts()
        current_resume_after_id = args.resume_after_id
        current_snapshot = before
        chunk_index = 0
        ran_summary_only_chunk = False

        while True:
            if args.max_chunks is not None and chunk_index >= args.max_chunks:
                break

            chunk_index += 1
            segmentation = _run_segment_city(
                city,
                limit=args.segment_limit,
                resume_after_id=current_resume_after_id,
                workers=args.segment_workers,
                segment_mode=args.segment_mode,
                agenda_timeout_seconds=args.agenda_timeout_seconds,
                emit_progress=human_progress,
                chunk_index=chunk_index,
            )
            should_run_summary = segmentation["catalog_count"] > 0 or (
                not ran_summary_only_chunk and current_snapshot["missing_summary_total"] > 0
            )
            if should_run_summary:
                _emit_progress(
                    human_progress,
                    f"[{city}] summary_start chunk={chunk_index} limit={summary_limit}",
                )
                summary = run_summary_hydration_backfill(
                    force=args.force,
                    limit=summary_limit,
                    city=city,
                    summary_timeout_seconds=args.summary_timeout_seconds,
                    summary_fallback_mode=args.summary_fallback_mode,
                )
                _emit_progress(human_progress, f"[{city}] summary_finish chunk={chunk_index} results={summary}")
            else:
                summary = _empty_summary_counts()

            after = _snapshot_dict(city)
            delta = _delta(current_snapshot, after)
            chunk = {
                "chunk_index": chunk_index,
                "resume_after_id": current_resume_after_id,
                "segmentation": segmentation,
                "summary": summary,
                "after": after,
                "delta": delta,
            }
            chunks.append(chunk)
            segmentation_total = {
                "city": city,
                "catalog_count": int(segmentation_total["catalog_count"]) + int(segmentation["catalog_count"]),
                "complete": int(segmentation_total["complete"]) + int(segmentation["complete"]),
                "empty": int(segmentation_total["empty"]) + int(segmentation["empty"]),
                "failed": int(segmentation_total["failed"]) + int(segmentation["failed"]),
                "timed_out": int(segmentation_total["timed_out"]) + int(segmentation["timed_out"]),
                "other": int(segmentation_total["other"]) + int(segmentation["other"]),
                "timeout_fallbacks": int(segmentation_total["timeout_fallbacks"]) + int(segmentation["timeout_fallbacks"]),
                "empty_response_fallbacks": int(segmentation_total["empty_response_fallbacks"]) + int(segmentation["empty_response_fallbacks"]),
                "llm_attempted": int(segmentation_total["llm_attempted"]) + int(segmentation["llm_attempted"]),
                "llm_skipped_heuristic_first": int(segmentation_total["llm_skipped_heuristic_first"]) + int(segmentation["llm_skipped_heuristic_first"]),
                "heuristic_complete": int(segmentation_total["heuristic_complete"]) + int(segmentation["heuristic_complete"]),
                "llm_timeout_then_fallback": int(segmentation_total["llm_timeout_then_fallback"]) + int(segmentation["llm_timeout_then_fallback"]),
            }
            summary_total = _merge_counts(summary_total, summary)
            _emit_progress(
                human_progress,
                "[{city}] chunk_finish chunk={chunk} after_missing_summary_total={missing} "
                "resume_after_id={resume_after_id} delta={delta}".format(
                    city=city,
                    chunk=chunk_index,
                    missing=after["missing_summary_total"],
                    resume_after_id=segmentation["last_catalog_id"],
                    delta=delta,
                ),
            )

            current_snapshot = after
            if segmentation["catalog_count"] > 0:
                current_resume_after_id = segmentation["last_catalog_id"]
                continue

            ran_summary_only_chunk = ran_summary_only_chunk or should_run_summary
            break

        after = current_snapshot
        delta = _delta(before, after)
        _emit_progress(
            human_progress,
            "[{city}] city_finish after_missing_summary_total={missing} catalogs_with_summary={summaries} delta={delta}".format(
                city=city,
                missing=after["missing_summary_total"],
                summaries=after["catalogs_with_summary"],
                delta=delta,
            ),
        )
        results.append(
            {
                "city": city,
                "before": before,
                "chunks": chunks,
                "segmentation": segmentation_total,
                "summary": summary_total,
                "after": after,
                "delta": delta,
            }
        )

    if args.json:
        print(json.dumps({"cities": results}, indent=2, sort_keys=True))
        return 0

    print("Staged City Hydration")
    print("=====================")
    for result in results:
        print(f"city: {result['city']}")
        print(f"  before_missing_summary_total: {result['before']['missing_summary_total']}")
        print(f"  after_missing_summary_total: {result['after']['missing_summary_total']}")
        print(f"  chunks: {len(result['chunks'])}")
        print(f"  segmentation: {result['segmentation']}")
        print(f"  summary: {result['summary']}")
        print(f"  delta: {result['delta']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

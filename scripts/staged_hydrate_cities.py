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


def _run_segment_city(city: str, *, emit_progress: bool = False) -> dict[str, Any]:
    from scripts import segment_city_corpus

    catalog_ids = segment_city_corpus._catalog_ids_for_city(city)
    if not catalog_ids:
        return {
            "city": city,
            "catalog_count": 0,
            "complete": 0,
            "empty": 0,
            "failed": 0,
            "timed_out": 0,
        }

    timeout_seconds = segment_city_corpus._catalog_timeout_seconds()
    counts = {"complete": 0, "empty": 0, "failed": 0, "timed_out": 0}
    total_catalogs = len(catalog_ids)
    _emit_progress(
        emit_progress,
        f"[{city}] segmentation_start catalog_count={total_catalogs} timeout_seconds={timeout_seconds}",
    )
    for index, catalog_id in enumerate(catalog_ids, start=1):
        _emit_progress(
            emit_progress,
            f"[{city}] segmentation_catalog_start index={index}/{total_catalogs} catalog_id={catalog_id}",
        )
        outcome, duration_seconds, _detail = segment_city_corpus._segment_catalog_subprocess(int(catalog_id), timeout_seconds)
        counts[outcome] += 1
        _emit_progress(
            emit_progress,
            "[{city}] segmentation_catalog_finish index={index}/{total_catalogs} catalog_id={catalog_id} "
            "outcome={outcome} duration_seconds={duration:.2f} running_counts={counts}".format(
                city=city,
                index=index,
                total_catalogs=total_catalogs,
                catalog_id=catalog_id,
                outcome=outcome,
                duration=duration_seconds,
                counts=counts,
            ),
        )
    return {"city": city, "catalog_count": total_catalogs, **counts}


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
    return {key: int(after[key]) - int(before[key]) for key in keys}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run staged city hydration: segment -> summarize -> diagnose")
    parser.add_argument("--city", action="append", dest="cities")
    parser.add_argument("--limit", type=int, default=None, help="Apply the same limit to summary backfill per city")
    parser.add_argument("--force", action="store_true", help="Force summary regeneration for selected cities")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON only")
    args = parser.parse_args()

    cities = args.cities or ordered_hydration_cities()
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
        segmentation = _run_segment_city(city, emit_progress=human_progress)
        _emit_progress(human_progress, f"[{city}] summary_start")
        summary = run_summary_hydration_backfill(force=args.force, limit=args.limit, city=city)
        _emit_progress(human_progress, f"[{city}] summary_finish results={summary}")
        after = _snapshot_dict(city)
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
                "segmentation": segmentation,
                "summary": summary,
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
        print(f"  segmentation: {result['segmentation']}")
        print(f"  summary: {result['summary']}")
        print(f"  delta: {result['delta']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

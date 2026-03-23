#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from typing import Any

from pipeline.city_scope import ordered_hydration_cities
from pipeline.db_session import db_session
from pipeline.summary_hydration_diagnostics import build_summary_hydration_snapshot
from pipeline.tasks import run_summary_hydration_backfill


def _run_segment_city(city: str) -> dict[str, Any]:
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
    for catalog_id in catalog_ids:
        outcome, _duration_seconds, _detail = segment_city_corpus._segment_catalog_subprocess(int(catalog_id), timeout_seconds)
        counts[outcome] += 1
    return {"city": city, "catalog_count": len(catalog_ids), **counts}


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
    results: list[dict[str, Any]] = []
    for city in cities:
        before = _snapshot_dict(city)
        segmentation = _run_segment_city(city)
        summary = run_summary_hydration_backfill(force=args.force, limit=args.limit, city=city)
        after = _snapshot_dict(city)
        results.append(
            {
                "city": city,
                "before": before,
                "segmentation": segmentation,
                "summary": summary,
                "after": after,
                "delta": _delta(before, after),
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

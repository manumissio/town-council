#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os

from pipeline.db_session import db_session
from pipeline.summary_hydration_diagnostics import build_summary_hydration_snapshot


def _database_url() -> str:
    return (os.getenv("DATABASE_URL") or "").strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnose why hydrated catalogs are missing summaries")
    parser.add_argument("--city")
    parser.add_argument("--sample-limit", type=int, default=5)
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON only")
    args = parser.parse_args()

    # This operator diagnostic must read the same configured database as the
    # running stack; fallback SQLite can produce stale or misleading backlog data.
    if not _database_url():
        print("ERROR: DATABASE_URL is not set.")
        print("Run this diagnostic in the configured pipeline environment, for example:")
        print("  docker compose run --rm pipeline python /app/scripts/diagnose_summary_hydration.py")
        print("  docker compose run --rm pipeline python /app/scripts/diagnose_summary_hydration.py --city san_mateo")
        print("  docker compose run --rm pipeline python /app/scripts/diagnose_summary_hydration.py --json")
        return 2

    with db_session() as session:
        snapshot = build_summary_hydration_snapshot(session, sample_limit=max(1, args.sample_limit), city=args.city)

    if args.json:
        print(json.dumps(snapshot.to_dict(), indent=2, sort_keys=True))
        return 0

    print("Summary Hydration Diagnostic")
    print("===========================")
    print(f"city: {snapshot.city or 'all'}")
    print("Cumulative totals")
    print(f"- catalogs_with_content: {snapshot.cumulative_catalogs_with_content}")
    print(f"- catalogs_with_summary: {snapshot.cumulative_catalogs_with_summary}")
    print("")
    print("Unresolved backlog totals")
    print(f"- missing_summary_total: {snapshot.unresolved_missing_summary_total}")
    print("")
    print("Backlog buckets (rows where summary is still null)")
    print(f"- agenda_missing_summary_total: {snapshot.agenda_missing_summary_total_unresolved}")
    print(f"- agenda_missing_summary_with_items: {snapshot.agenda_missing_summary_with_items_unresolved}")
    print(f"- agenda_missing_summary_without_items: {snapshot.agenda_missing_summary_without_items_unresolved}")
    print(f"- non_agenda_missing_summary_total: {snapshot.non_agenda_missing_summary_total_unresolved}")
    print(f"- non_agenda_summarizable: {snapshot.non_agenda_summarizable}")
    print(f"- non_agenda_blocked_low_signal: {snapshot.non_agenda_blocked_low_signal}")
    print("")
    print("Agenda segmentation status counts (unresolved backlog only)")
    for status, count in sorted((snapshot.agenda_unresolved_segmentation_status_counts or {}).items()):
        print(f"- {status}: {count}")
    print("")
    print("Interpretation note")
    print("- catalogs_with_summary is cumulative, while the backlog buckets above only include rows that still have summary = null.")
    print("")
    print("Sample catalog ids")
    for bucket, ids in snapshot.sample_catalog_ids.items():
        print(f"- {bucket}: {ids}")
    print("")
    print(f"likely_root_cause: {snapshot.likely_root_cause}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from pipeline.db_session import db_session
from pipeline.summary_hydration_diagnostics import build_summary_hydration_snapshot


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnose why hydrated catalogs are missing summaries")
    parser.add_argument("--city")
    parser.add_argument("--sample-limit", type=int, default=5)
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON only")
    args = parser.parse_args()

    with db_session() as session:
        snapshot = build_summary_hydration_snapshot(session, sample_limit=max(1, args.sample_limit), city=args.city)

    if args.json:
        print(json.dumps(snapshot.to_dict(), indent=2, sort_keys=True))
        return 0

    print("Summary Hydration Diagnostic")
    print("===========================")
    print(f"city: {snapshot.city or 'all'}")
    print(f"catalogs_with_content: {snapshot.catalogs_with_content}")
    print(f"catalogs_with_summary: {snapshot.catalogs_with_summary}")
    print(f"missing_summary_total: {snapshot.missing_summary_total}")
    print("")
    print("Backlog buckets")
    print(f"- agenda_missing_summary_total: {snapshot.agenda_missing_summary_total}")
    print(f"- agenda_missing_summary_with_items: {snapshot.agenda_missing_summary_with_items}")
    print(f"- agenda_missing_summary_without_items: {snapshot.agenda_missing_summary_without_items}")
    print(f"- non_agenda_missing_summary_total: {snapshot.non_agenda_missing_summary_total}")
    print(f"- non_agenda_summarizable: {snapshot.non_agenda_summarizable}")
    print(f"- non_agenda_blocked_low_signal: {snapshot.non_agenda_blocked_low_signal}")
    print("")
    print("Agenda segmentation status counts")
    for status, count in sorted(snapshot.agenda_segmentation_status_counts.items()):
        print(f"- {status}: {count}")
    print("")
    print("Sample catalog ids")
    for bucket, ids in snapshot.sample_catalog_ids.items():
        print(f"- {bucket}: {ids}")
    print("")
    print(f"likely_root_cause: {snapshot.likely_root_cause}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

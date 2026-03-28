#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime
import json

from pipeline.city_coverage_audit import build_city_coverage_audit
from pipeline.db_session import db_session


def _parse_as_of(value: str):
    return datetime.strptime(value, "%Y-%m-%d").date()


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit city event and agenda coverage across a rolling window")
    parser.add_argument("--city", required=True)
    parser.add_argument("--months", type=int, default=12)
    parser.add_argument("--as-of", type=_parse_as_of)
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON only")
    args = parser.parse_args()

    if args.months <= 0:
        parser.error("--months must be positive")

    with db_session() as session:
        audit = build_city_coverage_audit(
            session,
            city=args.city,
            months=args.months,
            as_of=args.as_of,
        )

    if args.json:
        print(json.dumps(audit.to_dict(), indent=2, sort_keys=True))
        return 0

    print("City Coverage Audit")
    print("===================")
    print(f"city: {audit.city}")
    print(f"window: {audit.date_from} -> {audit.date_to} ({audit.months} months)")
    print(f"expected_monthly_event_baseline: {audit.expected_monthly_event_baseline:.2f}")
    print(
        "below_expected_cadence_threshold: "
        f"{audit.below_expected_cadence_threshold if audit.below_expected_cadence_threshold is not None else 'n/a'}"
    )
    print(f"expected_monthly_meeting_baseline: {audit.expected_monthly_meeting_baseline:.2f}")
    print(
        "below_expected_meeting_cadence_threshold: "
        f"{audit.below_expected_meeting_cadence_threshold if audit.below_expected_meeting_cadence_threshold is not None else 'n/a'}"
    )
    print("")
    print("Window totals")
    for key, value in audit.totals.items():
        print(f"- {key}: {value}")
    print("")
    print("Source event totals")
    for source, value in audit.source_counts.items():
        print(f"- {source}: {value}")
    print("")
    print("Monthly coverage")
    for row in audit.monthly:
        flags = ",".join(row.flags) if row.flags else "ok"
        print(
            f"- {row.month}: "
            f"events={row.event_count} "
            f"meetings={row.meeting_count} "
            f"agenda_docs={row.agenda_document_count} "
            f"agenda_catalogs={row.agenda_catalog_count} "
            f"content={row.agenda_catalogs_with_content} "
            f"summaries={row.agenda_catalogs_with_summary} "
            f"event_sources={row.source_event_counts} "
            f"meeting_sources={row.source_meeting_counts} "
            f"flags={flags}"
        )
    print("")
    print("Suspicious months")
    if not audit.suspicious_months:
        print("- none")
    else:
        for row in audit.suspicious_months:
            print(f"- {row['month']}: {','.join(row['flags'])}")
    print("")
    print("Interpretation note")
    print(
        "- This audit measures source and downstream artifact coverage across the requested event window. "
        "It is not a summary-backlog diagnostic."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

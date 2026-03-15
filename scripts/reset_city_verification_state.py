#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import selectinload

from pipeline.db_session import db_session
from pipeline.models import Catalog, DataIssue, Document, Event


ISO_FMT = "%Y-%m-%dT%H:%M:%SZ"


@dataclass(frozen=True)
class RewindCounts:
    event_ids: list[int]
    document_ids: list[int]
    catalog_ids: list[int]
    unreferenced_catalog_ids: list[int]
    data_issue_ids: list[int]


def _parse_iso_utc(value: str) -> datetime:
    dt = datetime.strptime(value, ISO_FMT)
    return dt.replace(tzinfo=timezone.utc).replace(tzinfo=None)


def _ocd_division_id_for_city(city: str) -> str:
    return f"ocd-division/country:us/state:ca/place:{city}"


def _collect_rewind_counts(session, city: str, since_dt: datetime) -> RewindCounts:
    ocd_division_id = _ocd_division_id_for_city(city)
    events = (
        session.query(Event)
        .options(selectinload(Event.documents))
        .filter(
            Event.ocd_division_id == ocd_division_id,
            Event.scraped_datetime >= since_dt,
        )
        .all()
    )

    event_ids = [event.id for event in events]
    document_ids = [document.id for event in events for document in event.documents]
    catalog_ids = sorted({document.catalog_id for event in events for document in event.documents if document.catalog_id is not None})
    data_issue_ids = [row[0] for row in session.query(DataIssue.id).filter(DataIssue.event_id.in_(event_ids)).all()] if event_ids else []

    unreferenced_catalog_ids: list[int] = []
    if catalog_ids:
        # Catalog rows may survive document deletion in the DB, so only remove
        # catalogs whose entire reference set belongs to the rewound city window.
        ref_counts = {
            row.catalog_id: row.ref_count
            for row in (
                session.query(Document.catalog_id, func.count(Document.id).label("ref_count"))
                .filter(Document.catalog_id.in_(catalog_ids))
                .group_by(Document.catalog_id)
                .all()
            )
        }
        targeted_counts = {
            row.catalog_id: row.ref_count
            for row in (
                session.query(Document.catalog_id, func.count(Document.id).label("ref_count"))
                .filter(Document.id.in_(document_ids))
                .group_by(Document.catalog_id)
                .all()
            )
        }
        unreferenced_catalog_ids = sorted(
            catalog_id
            for catalog_id in catalog_ids
            if ref_counts.get(catalog_id, 0) == targeted_counts.get(catalog_id, 0)
        )

    return RewindCounts(
        event_ids=event_ids,
        document_ids=document_ids,
        catalog_ids=catalog_ids,
        unreferenced_catalog_ids=unreferenced_catalog_ids,
        data_issue_ids=data_issue_ids,
    )


def _remaining_anchor_summary(session, city: str) -> dict[str, str | int | None]:
    ocd_division_id = _ocd_division_id_for_city(city)
    max_record_date, max_scraped_datetime, remaining_event_count = (
        session.query(
            func.max(Event.record_date),
            func.max(Event.scraped_datetime),
            func.count(Event.id),
        )
        .filter(Event.ocd_division_id == ocd_division_id)
        .one()
    )
    return {
        "remaining_event_count": int(remaining_event_count or 0),
        "remaining_max_record_date": max_record_date.isoformat() if max_record_date else None,
        "remaining_max_scraped_datetime": max_scraped_datetime.strftime(ISO_FMT) if max_scraped_datetime else None,
    }


def reset_city_verification_state(city: str, since: str, *, dry_run: bool = False) -> dict[str, int | str | bool | None]:
    since_dt = _parse_iso_utc(since)

    with db_session() as session:
        counts = _collect_rewind_counts(session, city, since_dt)
        summary: dict[str, int | str | bool | None] = {
            "city": city,
            "since": since,
            "dry_run": dry_run,
            "deleted_event_count": len(counts.event_ids),
            "deleted_document_count": len(counts.document_ids),
            "deleted_catalog_count": len(counts.unreferenced_catalog_ids),
            "catalog_reference_count": len(counts.catalog_ids),
            "deleted_data_issue_count": len(counts.data_issue_ids),
        }

        if not dry_run:
            if counts.data_issue_ids:
                session.query(DataIssue).filter(DataIssue.id.in_(counts.data_issue_ids)).delete(
                    synchronize_session=False
                )

            if counts.event_ids:
                for event in (
                    session.query(Event)
                    .options(selectinload(Event.documents))
                    .filter(Event.id.in_(counts.event_ids))
                    .all()
                ):
                    session.delete(event)

            if counts.unreferenced_catalog_ids:
                for catalog in session.query(Catalog).filter(Catalog.id.in_(counts.unreferenced_catalog_ids)).all():
                    session.delete(catalog)

            session.commit()

        summary.update(_remaining_anchor_summary(session, city))
        return summary


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Delete city verification-era state created during a first-time onboarding window."
    )
    parser.add_argument("--city", required=True)
    parser.add_argument("--since", required=True)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report matching rows without deleting them.",
    )
    args = parser.parse_args()

    print(json.dumps(reset_city_verification_state(args.city, args.since, dry_run=args.dry_run), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

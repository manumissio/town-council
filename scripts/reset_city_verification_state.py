#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import date, datetime, timezone

from sqlalchemy import and_, func, or_
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


@dataclass(frozen=True)
class VerificationBaseline:
    city: str
    baseline_event_count: int
    baseline_max_record_date: date | None
    baseline_max_scraped_datetime: datetime | None


def _parse_iso_utc(value: str) -> datetime:
    dt = datetime.strptime(value, ISO_FMT)
    return dt.replace(tzinfo=timezone.utc).replace(tzinfo=None)


def _ocd_division_id_for_city(city: str) -> str:
    return f"ocd-division/country:us/state:ca/place:{city}"


def _rewind_counts_from_events(session, events: list[Event]) -> RewindCounts:
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
    return _rewind_counts_from_events(session, events)


def _collect_anchor_rewind_counts(
    session,
    city: str,
    since_dt: datetime,
    baseline_record_date: date | None,
) -> RewindCounts:
    ocd_division_id = _ocd_division_id_for_city(city)
    query = session.query(Event).options(selectinload(Event.documents)).filter(Event.ocd_division_id == ocd_division_id)
    if baseline_record_date is None:
        events = query.filter(Event.scraped_datetime >= since_dt).all()
    else:
        events = query.filter(
            or_(
                Event.record_date > baseline_record_date,
                and_(
                    Event.record_date == baseline_record_date,
                    Event.scraped_datetime >= since_dt,
                ),
            )
        ).all()
    return _rewind_counts_from_events(session, events)


def capture_city_verification_baseline(city: str) -> dict[str, str | int | None]:
    with db_session() as session:
        ocd_division_id = _ocd_division_id_for_city(city)
        max_record_date, max_scraped_datetime, event_count = (
            session.query(
                func.max(Event.record_date),
                func.max(Event.scraped_datetime),
                func.count(Event.id),
            )
            .filter(Event.ocd_division_id == ocd_division_id)
            .one()
        )
        baseline = VerificationBaseline(
            city=city,
            baseline_event_count=int(event_count or 0),
            baseline_max_record_date=max_record_date,
            baseline_max_scraped_datetime=max_scraped_datetime,
        )
        return {
            "city": baseline.city,
            "baseline_event_count": baseline.baseline_event_count,
            "baseline_max_record_date": baseline.baseline_max_record_date.isoformat()
            if baseline.baseline_max_record_date
            else None,
            "baseline_max_scraped_datetime": baseline.baseline_max_scraped_datetime.strftime(ISO_FMT)
            if baseline.baseline_max_scraped_datetime
            else None,
        }


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


def reset_city_verification_state(
    city: str,
    since: str,
    *,
    dry_run: bool = False,
    baseline_record_date: str | None = None,
) -> dict[str, int | str | bool | None]:
    since_dt = _parse_iso_utc(since)
    baseline_record_date_value = date.fromisoformat(baseline_record_date) if baseline_record_date else None

    with db_session() as session:
        if baseline_record_date_value is None:
            counts = _collect_rewind_counts(session, city, since_dt)
        else:
            counts = _collect_anchor_rewind_counts(session, city, since_dt, baseline_record_date_value)
        summary: dict[str, int | str | bool | None] = {
            "city": city,
            "since": since,
            "dry_run": dry_run,
            "baseline_record_date": baseline_record_date,
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
    parser.add_argument("--since")
    parser.add_argument(
        "--print-baseline",
        action="store_true",
        help="Print the city's current verification baseline instead of deleting rows.",
    )
    parser.add_argument(
        "--baseline-record-date",
        help="Optional record_date anchor used to restore first-time retry state.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report matching rows without deleting them.",
    )
    args = parser.parse_args()

    if args.print_baseline:
        print(json.dumps(capture_city_verification_baseline(args.city), sort_keys=True))
        return 0

    if not args.since:
        parser.error("--since is required unless --print-baseline is set")

    print(
        json.dumps(
            reset_city_verification_state(
                args.city,
                args.since,
                dry_run=args.dry_run,
                baseline_record_date=args.baseline_record_date,
            ),
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import selectinload

from pipeline.db_session import db_session
from pipeline.models import Event
from scripts import city_state_mutation


ISO_FMT = "%Y-%m-%dT%H:%M:%SZ"


@dataclass(frozen=True)
class VerificationBaseline:
    city: str
    baseline_event_count: int
    baseline_max_record_date: date | None
    baseline_max_scraped_datetime: datetime | None


def _parse_iso_utc(value: str) -> datetime:
    return datetime.strptime(value, ISO_FMT).replace(tzinfo=UTC)


def _format_iso_utc(value: datetime) -> str:
    aware_value = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return aware_value.astimezone(UTC).strftime(ISO_FMT)


def _collect_rewind_counts(
    session,
    city: str,
    since_dt: datetime,
) -> city_state_mutation.CityEventGraphMutation:
    ocd_division_id = city_state_mutation.city_ocd_division_id(city)
    events = (
        session.query(Event)
        .options(selectinload(Event.documents))
        .filter(
            Event.ocd_division_id == ocd_division_id,
            Event.scraped_datetime >= since_dt,
        )
        .all()
    )
    return city_state_mutation.collect_event_graph_mutation(session, events)


def _collect_anchor_rewind_counts(
    session,
    city: str,
    since_dt: datetime,
    baseline_record_date: date | None,
) -> city_state_mutation.CityEventGraphMutation:
    ocd_division_id = city_state_mutation.city_ocd_division_id(city)
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
    return city_state_mutation.collect_event_graph_mutation(session, events)


def capture_city_verification_baseline(city: str) -> dict[str, str | int | None]:
    with db_session() as session:
        ocd_division_id = city_state_mutation.city_ocd_division_id(city)
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
            "baseline_max_scraped_datetime": _format_iso_utc(baseline.baseline_max_scraped_datetime)
            if baseline.baseline_max_scraped_datetime
            else None,
        }


def _remaining_anchor_summary(session, city: str) -> dict[str, str | int | None]:
    ocd_division_id = city_state_mutation.city_ocd_division_id(city)
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
        "remaining_max_scraped_datetime": _format_iso_utc(max_scraped_datetime) if max_scraped_datetime else None,
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
            city_state_mutation.delete_event_graph(session, counts)
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

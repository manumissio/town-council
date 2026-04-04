#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass

from sqlalchemy import func
from sqlalchemy.orm import selectinload

from pipeline.db_session import db_session
from pipeline.models import Catalog, DataIssue, Document, Event, EventStage, UrlStage, UrlStageHist
from pipeline.rollout_registry import CITY_SLUG_RE


@dataclass(frozen=True)
class FlushCounts:
    event_stage_ids: list[int]
    url_stage_ids: list[int]
    url_stage_hist_ids: list[int]
    event_ids: list[int]
    document_ids: list[int]
    catalog_ids: list[int]
    unreferenced_catalog_ids: list[int]
    data_issue_ids: list[int]


def _ocd_division_id_for_city(city: str) -> str:
    return f"ocd-division/country:us/state:ca/place:{city}"


def _validate_city_slug(city: str) -> None:
    if not CITY_SLUG_RE.match(city):
        raise ValueError(f"invalid city slug: {city}")


def _collect_stage_ids(session, city: str) -> tuple[list[int], list[int], list[int]]:
    ocd_division_id = _ocd_division_id_for_city(city)
    event_stage_ids = [row[0] for row in session.query(EventStage.id).filter(EventStage.ocd_division_id == ocd_division_id).all()]
    url_stage_ids = [row[0] for row in session.query(UrlStage.id).filter(UrlStage.ocd_division_id == ocd_division_id).all()]
    url_stage_hist_ids = [
        row[0]
        for row in session.query(UrlStageHist.id).filter(UrlStageHist.ocd_division_id == ocd_division_id).all()
    ]
    return event_stage_ids, url_stage_ids, url_stage_hist_ids


def _collect_live_ids(session, city: str) -> tuple[list[int], list[int], list[int], list[int], list[int]]:
    ocd_division_id = _ocd_division_id_for_city(city)
    events = (
        session.query(Event)
        .options(selectinload(Event.documents))
        .filter(Event.ocd_division_id == ocd_division_id)
        .all()
    )
    event_ids = [event.id for event in events]
    document_ids = [document.id for event in events for document in event.documents]
    catalog_ids = sorted(
        {document.catalog_id for event in events for document in event.documents if document.catalog_id is not None}
    )
    data_issue_ids = (
        [row[0] for row in session.query(DataIssue.id).filter(DataIssue.event_id.in_(event_ids)).all()] if event_ids else []
    )

    unreferenced_catalog_ids: list[int] = []
    if catalog_ids:
        # A city flush should not delete a catalog that is still linked to another city.
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

    return event_ids, document_ids, catalog_ids, unreferenced_catalog_ids, data_issue_ids


def _collect_flush_counts(session, city: str) -> FlushCounts:
    event_stage_ids, url_stage_ids, url_stage_hist_ids = _collect_stage_ids(session, city)
    event_ids, document_ids, catalog_ids, unreferenced_catalog_ids, data_issue_ids = _collect_live_ids(session, city)
    return FlushCounts(
        event_stage_ids=event_stage_ids,
        url_stage_ids=url_stage_ids,
        url_stage_hist_ids=url_stage_hist_ids,
        event_ids=event_ids,
        document_ids=document_ids,
        catalog_ids=catalog_ids,
        unreferenced_catalog_ids=unreferenced_catalog_ids,
        data_issue_ids=data_issue_ids,
    )


def _remaining_summary(session, city: str) -> dict[str, int]:
    ocd_division_id = _ocd_division_id_for_city(city)
    remaining_event_count = session.query(func.count(Event.id)).filter(Event.ocd_division_id == ocd_division_id).scalar() or 0
    remaining_document_count = (
        session.query(func.count(Document.id))
        .join(Event, Event.id == Document.event_id)
        .filter(Event.ocd_division_id == ocd_division_id)
        .scalar()
        or 0
    )
    remaining_catalog_count = (
        session.query(func.count(func.distinct(Catalog.id)))
        .join(Document, Document.catalog_id == Catalog.id)
        .join(Event, Event.id == Document.event_id)
        .filter(Event.ocd_division_id == ocd_division_id)
        .scalar()
        or 0
    )
    remaining_event_stage_count = (
        session.query(func.count(EventStage.id)).filter(EventStage.ocd_division_id == ocd_division_id).scalar() or 0
    )
    remaining_url_stage_count = (
        session.query(func.count(UrlStage.id)).filter(UrlStage.ocd_division_id == ocd_division_id).scalar() or 0
    )
    remaining_url_stage_hist_count = (
        session.query(func.count(UrlStageHist.id)).filter(UrlStageHist.ocd_division_id == ocd_division_id).scalar() or 0
    )
    return {
        "remaining_event_count": int(remaining_event_count),
        "remaining_document_count": int(remaining_document_count),
        "remaining_catalog_count": int(remaining_catalog_count),
        "remaining_event_stage_count": int(remaining_event_stage_count),
        "remaining_url_stage_count": int(remaining_url_stage_count),
        "remaining_url_stage_hist_count": int(remaining_url_stage_hist_count),
    }


def flush_city_pipeline_state(city: str, *, dry_run: bool = True) -> dict[str, int | str | bool]:
    _validate_city_slug(city)
    with db_session() as session:
        counts = _collect_flush_counts(session, city)
        summary: dict[str, int | str | bool] = {
            "city": city,
            "dry_run": dry_run,
            "deleted_event_stage_count": len(counts.event_stage_ids),
            "deleted_url_stage_count": len(counts.url_stage_ids),
            "deleted_url_stage_hist_count": len(counts.url_stage_hist_ids),
            "deleted_event_count": len(counts.event_ids),
            "deleted_document_count": len(counts.document_ids),
            "deleted_catalog_count": len(counts.unreferenced_catalog_ids),
            "catalog_reference_count": len(counts.catalog_ids),
            "deleted_data_issue_count": len(counts.data_issue_ids),
        }

        if not dry_run:
            if counts.data_issue_ids:
                session.query(DataIssue).filter(DataIssue.id.in_(counts.data_issue_ids)).delete(synchronize_session=False)
            if counts.event_stage_ids:
                session.query(EventStage).filter(EventStage.id.in_(counts.event_stage_ids)).delete(synchronize_session=False)
            if counts.url_stage_ids:
                session.query(UrlStage).filter(UrlStage.id.in_(counts.url_stage_ids)).delete(synchronize_session=False)
            if counts.url_stage_hist_ids:
                session.query(UrlStageHist).filter(UrlStageHist.id.in_(counts.url_stage_hist_ids)).delete(
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

        summary.update(_remaining_summary(session, city))
        return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Flush city-scoped staging and live pipeline state.")
    parser.add_argument("--city", required=True)
    parser.add_argument("--apply", action="store_true", help="Apply the flush. Without this flag the command is dry-run only.")
    args = parser.parse_args()

    print(json.dumps(flush_city_pipeline_state(args.city, dry_run=not args.apply), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

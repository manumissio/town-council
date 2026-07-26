#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass

from sqlalchemy import func
from sqlalchemy.orm import selectinload

from pipeline.db_session import db_session
from pipeline.models import Catalog, Document, Event, EventStage, UrlStage, UrlStageHist
from pipeline.rollout_registry import CITY_SLUG_RE
from scripts import city_state_mutation


@dataclass(frozen=True)
class FlushCounts:
    event_stage_ids: list[int]
    url_stage_ids: list[int]
    url_stage_hist_ids: list[int]
    event_graph: city_state_mutation.CityEventGraphMutation


def _validate_city_slug(city: str) -> None:
    if not CITY_SLUG_RE.match(city):
        raise ValueError(f"invalid city slug: {city}")


def _collect_stage_ids(session, city: str) -> tuple[list[int], list[int], list[int]]:
    ocd_division_id = city_state_mutation.city_ocd_division_id(city)
    event_stage_ids = [row[0] for row in session.query(EventStage.id).filter(EventStage.ocd_division_id == ocd_division_id).all()]
    url_stage_ids = [row[0] for row in session.query(UrlStage.id).filter(UrlStage.ocd_division_id == ocd_division_id).all()]
    url_stage_hist_ids = [
        row[0]
        for row in session.query(UrlStageHist.id).filter(UrlStageHist.ocd_division_id == ocd_division_id).all()
    ]
    return event_stage_ids, url_stage_ids, url_stage_hist_ids


def _collect_live_graph(session, city: str) -> city_state_mutation.CityEventGraphMutation:
    ocd_division_id = city_state_mutation.city_ocd_division_id(city)
    events = (
        session.query(Event)
        .options(selectinload(Event.documents))
        .filter(Event.ocd_division_id == ocd_division_id)
        .all()
    )
    return city_state_mutation.collect_event_graph_mutation(session, events)


def _collect_flush_counts(session, city: str) -> FlushCounts:
    event_stage_ids, url_stage_ids, url_stage_hist_ids = _collect_stage_ids(session, city)
    return FlushCounts(
        event_stage_ids=event_stage_ids,
        url_stage_ids=url_stage_ids,
        url_stage_hist_ids=url_stage_hist_ids,
        event_graph=_collect_live_graph(session, city),
    )


def _remaining_summary(session, city: str) -> dict[str, int]:
    ocd_division_id = city_state_mutation.city_ocd_division_id(city)
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
        event_graph = counts.event_graph
        summary: dict[str, int | str | bool] = {
            "city": city,
            "dry_run": dry_run,
            "deleted_event_stage_count": len(counts.event_stage_ids),
            "deleted_url_stage_count": len(counts.url_stage_ids),
            "deleted_url_stage_hist_count": len(counts.url_stage_hist_ids),
            "deleted_event_count": len(event_graph.event_ids),
            "deleted_document_count": len(event_graph.document_ids),
            "deleted_catalog_count": len(event_graph.unreferenced_catalog_ids),
            "catalog_reference_count": len(event_graph.catalog_ids),
            "deleted_data_issue_count": len(event_graph.data_issue_ids),
        }

        if not dry_run:
            if counts.event_stage_ids:
                session.query(EventStage).filter(EventStage.id.in_(counts.event_stage_ids)).delete(synchronize_session=False)
            if counts.url_stage_ids:
                session.query(UrlStage).filter(UrlStage.id.in_(counts.url_stage_ids)).delete(synchronize_session=False)
            if counts.url_stage_hist_ids:
                session.query(UrlStageHist).filter(UrlStageHist.id.in_(counts.url_stage_hist_ids)).delete(
                    synchronize_session=False
                )
            city_state_mutation.delete_event_graph(session, event_graph)
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

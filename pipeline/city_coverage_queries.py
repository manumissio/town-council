from __future__ import annotations

from datetime import date
from typing import NamedTuple

from sqlalchemy.orm import Session

from pipeline.city_coverage_buckets import (
    MonthlyCoverageBucket,
    add_agenda_to_monthly_bucket,
    add_event_to_monthly_bucket,
)
from pipeline.models import Catalog, Document, Event


class EventCoverageRow(NamedTuple):
    event_id: int
    record_date: date
    source: str
    name: str | None


class AgendaCoverageRow(NamedTuple):
    record_date: date
    document_id: int
    catalog_id: int | None
    content: str | None
    summary: str | None


def load_event_coverage_rows(
    db_session: Session,
    *,
    source_aliases: list[str],
    start_date: date,
    end_date: date,
) -> list[EventCoverageRow]:
    rows = (
        db_session.query(Event.id, Event.record_date, Event.source, Event.name)
        .filter(
            Event.source.in_(source_aliases),
            Event.record_date.isnot(None),
            Event.record_date >= start_date,
            Event.record_date <= end_date,
        )
        .all()
    )
    return [EventCoverageRow(int(event_id), record_date, str(source), name) for event_id, record_date, source, name in rows]


def load_agenda_coverage_rows(
    db_session: Session,
    *,
    source_aliases: list[str],
    start_date: date,
    end_date: date,
) -> list[AgendaCoverageRow]:
    rows = (
        db_session.query(
            Event.record_date,
            Document.id,
            Document.catalog_id,
            Catalog.content,
            Catalog.summary,
        )
        .join(Document, Document.event_id == Event.id)
        .outerjoin(Catalog, Catalog.id == Document.catalog_id)
        .filter(
            Event.source.in_(source_aliases),
            Event.record_date.isnot(None),
            Event.record_date >= start_date,
            Event.record_date <= end_date,
            Document.category == "agenda",
        )
        .all()
    )
    return [
        AgendaCoverageRow(record_date, int(document_id), catalog_id, content, summary)
        for record_date, document_id, catalog_id, content, summary in rows
    ]


def ingest_coverage_rows(
    buckets: dict[str, MonthlyCoverageBucket],
    *,
    event_rows: list[EventCoverageRow],
    agenda_rows: list[AgendaCoverageRow],
) -> None:
    for event_row in event_rows:
        add_event_to_monthly_bucket(
            buckets,
            event_id=event_row.event_id,
            record_date=event_row.record_date,
            source=event_row.source,
            name=event_row.name,
        )
    for agenda_row in agenda_rows:
        add_agenda_to_monthly_bucket(
            buckets,
            record_date=agenda_row.record_date,
            document_id=agenda_row.document_id,
            catalog_id=agenda_row.catalog_id,
            content=agenda_row.content,
            summary=agenda_row.summary,
        )

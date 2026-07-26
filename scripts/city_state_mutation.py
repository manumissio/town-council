from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from pipeline.models import Catalog, DataIssue, Document, Event


@dataclass(frozen=True)
class CityEventGraphMutation:
    event_ids: list[int]
    document_ids: list[int]
    catalog_ids: list[int]
    unreferenced_catalog_ids: list[int]
    data_issue_ids: list[int]


def city_ocd_division_id(city: str) -> str:
    return f"ocd-division/country:us/state:ca/place:{city}"


def _catalog_reference_counts(
    session: Session,
    catalog_ids: list[int],
    document_ids: list[int],
) -> tuple[dict[int, int], dict[int, int]]:
    reference_counts = {
        row.catalog_id: row.ref_count
        for row in (
            session.query(
                Document.catalog_id,
                func.count(Document.id).label("ref_count"),
            )
            .filter(Document.catalog_id.in_(catalog_ids))
            .group_by(Document.catalog_id)
            .all()
        )
    }
    selected_counts = {
        row.catalog_id: row.ref_count
        for row in (
            session.query(
                Document.catalog_id,
                func.count(Document.id).label("ref_count"),
            )
            .filter(Document.id.in_(document_ids))
            .group_by(Document.catalog_id)
            .all()
        )
    }
    return reference_counts, selected_counts


def _unreferenced_catalog_ids(
    session: Session,
    catalog_ids: list[int],
    document_ids: list[int],
) -> list[int]:
    if not catalog_ids:
        return []

    reference_counts, selected_counts = _catalog_reference_counts(
        session,
        catalog_ids,
        document_ids,
    )
    return sorted(
        catalog_id
        for catalog_id in catalog_ids
        if reference_counts.get(catalog_id, 0) == selected_counts.get(catalog_id, 0)
    )


def collect_event_graph_mutation(
    session: Session,
    selected_events: list[Event],
) -> CityEventGraphMutation:
    event_ids = [int(event.id) for event in selected_events]
    document_ids = [
        int(document.id)
        for event in selected_events
        for document in event.documents
    ]
    catalog_ids = sorted(
        {
            int(document.catalog_id)
            for event in selected_events
            for document in event.documents
            if document.catalog_id is not None
        }
    )
    data_issue_ids = (
        [
            row[0]
            for row in (
                session.query(DataIssue.id)
                .filter(DataIssue.event_id.in_(event_ids))
                .all()
            )
        ]
        if event_ids
        else []
    )
    return CityEventGraphMutation(
        event_ids=event_ids,
        document_ids=document_ids,
        catalog_ids=catalog_ids,
        unreferenced_catalog_ids=_unreferenced_catalog_ids(
            session,
            catalog_ids,
            document_ids,
        ),
        data_issue_ids=data_issue_ids,
    )


def delete_event_graph(
    session: Session,
    mutation: CityEventGraphMutation,
) -> None:
    if mutation.data_issue_ids:
        (
            session.query(DataIssue)
            .filter(DataIssue.id.in_(mutation.data_issue_ids))
            .delete(synchronize_session=False)
        )

    if mutation.event_ids:
        events = (
            session.query(Event)
            .options(selectinload(Event.documents))
            .filter(Event.id.in_(mutation.event_ids))
            .all()
        )
        for event in events:
            session.delete(event)

    if mutation.unreferenced_catalog_ids:
        catalogs = (
            session.query(Catalog)
            .filter(Catalog.id.in_(mutation.unreferenced_catalog_ids))
            .all()
        )
        for catalog in catalogs:
            session.delete(catalog)

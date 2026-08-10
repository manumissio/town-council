from __future__ import annotations

from importlib import import_module
from typing import Any

from sqlalchemy import Text, and_, cast, func, or_

from pipeline.profile_manifest_contracts import ManifestCandidate, OrmSession


def _models() -> Any:
    return import_module("pipeline.models")  # SQLAlchemy ORM models are runtime-loaded for typed boundary isolation.


def _summary_doc_kind_subquery(session: OrmSession) -> Any:
    queries = import_module("pipeline.summary_backfill_queries")
    return queries.summary_doc_kind_subquery(session)  # Reuse runtime routing without importing untyped query code.


def extract_candidates(session: OrmSession) -> list[ManifestCandidate]:
    models = _models()
    rows = (
        session.query(models.Catalog.id, models.Catalog.location)
        .join(models.Document, models.Document.catalog_id == models.Catalog.id)
        .filter(
            models.Document.category == "agenda",
            models.Catalog.location.is_not(None),
            models.Catalog.location != "",
            models.Catalog.content.is_not(None),
            models.Catalog.content != "",
            models.Catalog.extraction_status == "complete",
        )
        .order_by(models.Catalog.id)
        .distinct()
        .all()
    )
    return [
        {"catalog_id": int(catalog_id), "source_location": str(location) if location is not None else ""}
        for catalog_id, location in rows
    ]


def segment_reset_candidates(session: OrmSession) -> list[ManifestCandidate]:
    models = _models()
    rows = (
        session.query(models.Catalog.id)
        .join(models.Document, models.Document.catalog_id == models.Catalog.id)
        .filter(
            models.Catalog.content.is_not(None),
            models.Catalog.content != "",
            models.Catalog.agenda_segmentation_status == "complete",
        )
        .group_by(models.Catalog.id)
        .having(and_(func.count(models.Document.id) == 1, func.min(models.Document.category) == "agenda"))
        .order_by(models.Catalog.id)
        .all()
    )
    return [{"catalog_id": int(row[0])} for row in rows]


def summary_reset_candidates(session: OrmSession) -> list[ManifestCandidate]:
    models = _models()
    doc_kind = _summary_doc_kind_subquery(session)
    agenda_items_exist = (
        session.query(models.AgendaItem.id).filter(models.AgendaItem.catalog_id == models.Catalog.id).exists()
    )
    rows = (
        session.query(models.Catalog.id)
        .join(doc_kind, doc_kind.c.catalog_id == models.Catalog.id)
        .filter(
            models.Catalog.content.is_not(None),
            models.Catalog.content != "",
            models.Catalog.summary.is_not(None),
            or_(
                doc_kind.c.doc_kind != "agenda",
                agenda_items_exist,
                models.Catalog.agenda_segmentation_status == "empty",
            ),
        )
        .order_by(models.Catalog.id)
        .distinct()
        .all()
    )
    return [{"catalog_id": int(row[0])} for row in rows]


def entity_reset_candidates(session: OrmSession) -> list[ManifestCandidate]:
    models = _models()
    rows = (
        session.query(models.Catalog.id)
        .filter(
            models.Catalog.content.is_not(None),
            models.Catalog.content != "",
            models.Catalog.content_hash.is_not(None),
            models.Catalog.entities.is_not(None),
            cast(models.Catalog.entities, Text) != "null",
            models.Catalog.entities_source_hash == models.Catalog.content_hash,
        )
        .order_by(models.Catalog.id)
        .all()
    )
    return [{"catalog_id": int(row[0])} for row in rows]


def org_reset_candidates(session: OrmSession) -> list[ManifestCandidate]:
    models = _models()
    event_doc_counts = {
        int(event_id): int(count)
        for event_id, count in (
            session.query(models.Event.id, func.count(models.Document.id))
            .join(models.Document, models.Document.event_id == models.Event.id)
            .filter(models.Event.organization_id.is_not(None))
            .group_by(models.Event.id)
            .all()
        )
    }
    rows = (
        session.query(models.Catalog.id, models.Event.id)
        .join(models.Document, models.Document.catalog_id == models.Catalog.id)
        .join(models.Event, models.Event.id == models.Document.event_id)
        .filter(models.Event.organization_id.is_not(None))
        .order_by(models.Catalog.id)
        .all()
    )
    candidates: list[ManifestCandidate] = []
    for catalog_id, event_id in rows:
        eid = int(event_id)
        if event_doc_counts.get(eid) != 1:
            continue
        candidates.append({"catalog_id": int(catalog_id), "event_id": eid})
    return candidates

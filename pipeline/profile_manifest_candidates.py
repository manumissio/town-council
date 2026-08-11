from __future__ import annotations

from importlib import import_module
from typing import Any

from sqlalchemy import Text, and_, cast, func

from pipeline.content_hash import compute_content_hash
from pipeline.profile_manifest_contracts import ManifestCandidate, OrmSession
from pipeline.summary_freshness import compute_agenda_items_hash, is_summary_fresh


def _models() -> Any:
    return import_module("pipeline.models")  # SQLAlchemy ORM models are runtime-loaded for typed boundary isolation.


def _summary_doc_kind_subquery(session: OrmSession) -> Any:
    queries = import_module("pipeline.summary_backfill_queries")
    return queries.summary_doc_kind_subquery(session)  # Reuse runtime routing without importing untyped query code.


def _organization_name_for_meeting_type(meeting_type: str | None) -> str:
    organizations = import_module("pipeline.backfill_orgs")
    return str(organizations.organization_name_for_meeting_type(meeting_type))


def _single_agenda_document_condition(models: Any) -> Any:
    return and_(func.count(models.Document.id) == 1, func.min(models.Document.category) == "agenda")


def _content_hash_is_current(content: object, content_hash: object) -> bool:
    return isinstance(content, str) and isinstance(content_hash, str) and compute_content_hash(content) == content_hash


def _current_agenda_item_hashes(session: OrmSession, catalog_ids: list[int]) -> dict[int, str]:
    if not catalog_ids:
        return {}
    models = _models()
    agenda_items = (
        session.query(models.AgendaItem)
        .filter(models.AgendaItem.catalog_id.in_(catalog_ids))
        .order_by(models.AgendaItem.catalog_id, models.AgendaItem.order, models.AgendaItem.id)
        .all()
    )
    items_by_catalog: dict[int, list[Any]] = {}
    for agenda_item in agenda_items:
        items_by_catalog.setdefault(int(agenda_item.catalog_id), []).append(agenda_item)
    return {
        catalog_id: agenda_hash
        for catalog_id, catalog_items in items_by_catalog.items()
        if (agenda_hash := compute_agenda_items_hash(catalog_items)) is not None
    }


def extract_candidates(session: OrmSession) -> list[ManifestCandidate]:
    models = _models()
    rows = (
        session.query(
            models.Catalog.id,
            models.Catalog.location,
            models.Catalog.content,
            models.Catalog.content_hash,
        )
        .join(models.Document, models.Document.catalog_id == models.Catalog.id)
        .filter(
            models.Catalog.location.is_not(None),
            models.Catalog.location != "",
            models.Catalog.content.is_not(None),
            models.Catalog.content != "",
            models.Catalog.content_hash.is_not(None),
            models.Catalog.extraction_status == "complete",
        )
        .group_by(
            models.Catalog.id,
            models.Catalog.location,
            models.Catalog.content,
            models.Catalog.content_hash,
        )
        .having(_single_agenda_document_condition(models))
        .order_by(models.Catalog.id)
        .all()
    )
    return [
        {"catalog_id": int(catalog_id), "source_location": str(location) if location is not None else ""}
        for catalog_id, location, content, content_hash in rows
        if _content_hash_is_current(content, content_hash)
    ]


def segment_reset_candidates(session: OrmSession) -> list[ManifestCandidate]:
    models = _models()
    rows = (
        session.query(
            models.Catalog.id,
            models.Catalog.content,
            models.Catalog.content_hash,
            models.Catalog.agenda_items_hash,
        )
        .join(models.Document, models.Document.catalog_id == models.Catalog.id)
        .filter(
            models.Catalog.content.is_not(None),
            models.Catalog.content != "",
            models.Catalog.content_hash.is_not(None),
            models.Catalog.agenda_segmentation_status == "complete",
            models.Catalog.agenda_items_hash.is_not(None),
        )
        .group_by(
            models.Catalog.id,
            models.Catalog.content,
            models.Catalog.content_hash,
            models.Catalog.agenda_items_hash,
        )
        .having(_single_agenda_document_condition(models))
        .order_by(models.Catalog.id)
        .all()
    )
    candidate_ids = [int(catalog_id) for catalog_id, _content, _content_hash, _agenda_items_hash in rows]
    missing_page_ids = {
        int(catalog_id)
        for (catalog_id,) in session.query(models.AgendaItem.catalog_id)
        .filter(
            models.AgendaItem.catalog_id.in_(candidate_ids),
            models.AgendaItem.page_number.is_(None),
        )
        .distinct()
        .all()
    }
    current_hashes = _current_agenda_item_hashes(session, candidate_ids)
    return [
        {"catalog_id": int(catalog_id)}
        for catalog_id, content, content_hash, stored_hash in rows
        if _content_hash_is_current(content, content_hash)
        and int(catalog_id) not in missing_page_ids
        and current_hashes.get(int(catalog_id)) == stored_hash
    ]


def summary_reset_candidates(session: OrmSession) -> list[ManifestCandidate]:
    models = _models()
    doc_kind = _summary_doc_kind_subquery(session)
    rows = (
        session.query(
            models.Catalog.id,
            models.Catalog.content,
            doc_kind.c.doc_kind,
            models.Catalog.summary,
            models.Catalog.summary_source_hash,
            models.Catalog.content_hash,
            models.Catalog.agenda_items_hash,
            models.Catalog.agenda_segmentation_status,
        )
        .join(doc_kind, doc_kind.c.catalog_id == models.Catalog.id)
        .filter(
            models.Catalog.content.is_not(None),
            models.Catalog.content != "",
            models.Catalog.summary.is_not(None),
            models.Catalog.summary != "",
        )
        .order_by(models.Catalog.id)
        .all()
    )
    agenda_catalog_ids = [int(row[0]) for row in rows if row[2] == "agenda"]
    current_agenda_hashes = _current_agenda_item_hashes(session, agenda_catalog_ids)
    candidates: list[ManifestCandidate] = []
    for (
        catalog_id,
        content,
        kind,
        summary,
        summary_source_hash,
        content_hash,
        agenda_items_hash,
        segmentation_status,
    ) in rows:
        if not _content_hash_is_current(content, content_hash):
            continue
        current_agenda_hash = current_agenda_hashes.get(int(catalog_id))
        if kind == "agenda" and agenda_items_hash != current_agenda_hash:
            continue
        if is_summary_fresh(
            kind,
            summary=summary,
            summary_source_hash=summary_source_hash,
            content_hash=content_hash,
            agenda_items_hash=current_agenda_hash,
            agenda_segmentation_status=segmentation_status,
        ):
            candidates.append({"catalog_id": int(catalog_id)})
    return candidates


def entity_reset_candidates(session: OrmSession) -> list[ManifestCandidate]:
    models = _models()
    rows = (
        session.query(models.Catalog.id, models.Catalog.content, models.Catalog.content_hash)
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
    return [
        {"catalog_id": int(catalog_id)}
        for catalog_id, content, content_hash in rows
        if _content_hash_is_current(content, content_hash)
    ]


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
        session.query(
            models.Catalog.id,
            models.Event.id,
            models.Event.place_id,
            models.Event.meeting_type,
            models.Event.organization_id,
        )
        .join(models.Document, models.Document.catalog_id == models.Catalog.id)
        .join(models.Event, models.Event.id == models.Document.event_id)
        .filter(models.Event.organization_id.is_not(None))
        .order_by(models.Catalog.id)
        .all()
    )
    place_ids = sorted({int(place_id) for _catalog_id, _event_id, place_id, _meeting_type, _org_id in rows})
    organization_ids_by_key: dict[tuple[int, str], list[int]] = {}
    for organization_id, place_id, name in (
        session.query(models.Organization.id, models.Organization.place_id, models.Organization.name)
        .filter(models.Organization.place_id.in_(place_ids))
        .all()
    ):
        key = (int(place_id), str(name))
        organization_ids_by_key.setdefault(key, []).append(int(organization_id))
    candidates: list[ManifestCandidate] = []
    for catalog_id, event_id, place_id, meeting_type, organization_id in rows:
        eid = int(event_id)
        if event_doc_counts.get(eid) != 1:
            continue
        expected_name = _organization_name_for_meeting_type(meeting_type)
        matching_organization_ids = organization_ids_by_key.get((int(place_id), expected_name), [])
        if len(matching_organization_ids) != 1 or matching_organization_ids[0] != int(organization_id):
            continue
        candidates.append({"catalog_id": int(catalog_id), "event_id": eid})
    return candidates

from __future__ import annotations

from collections.abc import Callable
from importlib import import_module
from typing import Any, TypeAlias

from sqlalchemy import func

from pipeline.profile_manifest_contracts import ManifestCandidate, OrmSession


def _models() -> Any:
    return import_module("pipeline.models")  # SQLAlchemy ORM models are runtime-loaded for typed boundary isolation.


def _run_pipeline() -> Any:
    return import_module("pipeline.run_pipeline")  # Facade owns onboarding-aware selector defaults.


Selector: TypeAlias = Callable[[OrmSession], list[int]]


def extract_candidates(
    session: OrmSession,
    *,
    models_module: Any | None = None,  # SQLAlchemy model module is dynamic at runtime.
    processing_selector: Selector | None = None,
) -> list[ManifestCandidate]:
    models = models_module or _models()
    selector = processing_selector or _run_pipeline().select_catalog_ids_for_processing
    ids = [int(cid) for cid in selector(session)]
    if not ids:
        return []
    rows = (
        session.query(models.Catalog.id)
        .join(models.Document, models.Document.catalog_id == models.Catalog.id)
        .filter(models.Catalog.id.in_(ids), models.Document.category == "agenda")
        .order_by(models.Catalog.id)
        .distinct()
        .all()
    )
    return [{"catalog_id": int(row[0])} for row in rows]


def segment_reset_candidates(
    session: OrmSession,
    *,
    models_module: Any | None = None,  # SQLAlchemy model module is dynamic at runtime.
) -> list[ManifestCandidate]:
    models = models_module or _models()
    rows = (
        session.query(models.Catalog.id)
        .join(models.Document, models.Document.catalog_id == models.Catalog.id)
        .filter(
            models.Document.category == "agenda",
            models.Catalog.content.is_not(None),
            models.Catalog.agenda_segmentation_status == "complete",
        )
        .order_by(models.Catalog.id)
        .distinct()
        .all()
    )
    return [{"catalog_id": int(row[0])} for row in rows]


def summary_reset_candidates(
    session: OrmSession,
    *,
    models_module: Any | None = None,  # SQLAlchemy model module is dynamic at runtime.
) -> list[ManifestCandidate]:
    models = models_module or _models()
    agenda_item_catalog_ids = {
        int(row[0]) for row in session.query(models.AgendaItem.catalog_id).distinct().all() if row[0] is not None
    }
    rows = (
        session.query(models.Catalog.id, models.Document.category)
        .join(models.Document, models.Document.catalog_id == models.Catalog.id)
        .filter(models.Catalog.content.is_not(None), models.Catalog.summary.is_not(None))
        .order_by(models.Catalog.id)
        .distinct()
        .all()
    )
    candidates: list[ManifestCandidate] = []
    for catalog_id, category in rows:
        cid = int(catalog_id)
        if category in {"agenda", "agenda_html"} and cid not in agenda_item_catalog_ids:
            continue
        candidates.append({"catalog_id": cid})
    return candidates


def entity_reset_candidates(
    session: OrmSession,
    *,
    models_module: Any | None = None,  # SQLAlchemy model module is dynamic at runtime.
    entity_selector: Selector | None = None,
) -> list[ManifestCandidate]:
    models = models_module or _models()
    selector = entity_selector or _run_pipeline().select_catalog_ids_for_entity_backfill
    ids = [int(cid) for cid in selector(session)]
    if ids:
        return [{"catalog_id": cid} for cid in ids]

    rows = (
        session.query(models.Catalog.id)
        .join(models.Document, models.Document.catalog_id == models.Catalog.id)
        .filter(models.Catalog.content.is_not(None), models.Catalog.entities.is_not(None))
        .order_by(models.Catalog.id)
        .distinct()
        .all()
    )
    return [{"catalog_id": int(row[0])} for row in rows]


def org_reset_candidates(
    session: OrmSession,
    *,
    models_module: Any | None = None,  # SQLAlchemy model module is dynamic at runtime.
) -> list[ManifestCandidate]:
    models = models_module or _models()
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

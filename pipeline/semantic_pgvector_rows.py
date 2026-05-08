from __future__ import annotations

from typing import Any

from pipeline.models import Catalog, Document, Event, Organization, Place
from pipeline.semantic_text import catalog_semantic_source_hash, catalog_semantic_text


def _collect_catalog_summary_rows(backend, db) -> list[dict[str, Any]]:
    rows = (
        db.query(Document, Catalog, Event, Place, Organization)
        .join(Catalog, Document.catalog_id == Catalog.id)
        .join(Event, Document.event_id == Event.id)
        .join(Place, Document.place_id == Place.id)
        .outerjoin(Organization, Event.organization_id == Organization.id)
        .filter(Catalog.summary.isnot(None))
        .all()
    )
    catalog_summary_rows: list[dict[str, Any]] = []
    seen_catalogs: set[int] = set()
    for doc, catalog, event, place, org in rows:
        if catalog.id in seen_catalogs:
            continue
        seen_catalogs.add(catalog.id)
        source_hash = catalog_semantic_source_hash(catalog.summary)
        if source_hash is None:
            continue
        catalog_summary_rows.append(
            {
                "catalog_id": catalog.id,
                "doc_id": doc.id,
                "event_id": event.id,
                "city": (place.display_name or place.name or "").lower(),
                "meeting_category": event.meeting_type or "Other",
                "organization": org.name if org else "City Council",
                "date": event.record_date.isoformat() if event.record_date else None,
                "text": catalog_semantic_text(catalog.summary),
                "source_hash": source_hash,
            }
        )
    return catalog_summary_rows

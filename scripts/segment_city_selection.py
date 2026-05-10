from __future__ import annotations

from sqlalchemy import and_, func, or_

from pipeline.models import AgendaItem, Catalog, Document, Event
from scripts.segment_city_contracts import SegmentSelectionServices


def html_location_predicate(column: object) -> object:
    lowered_location = func.lower(func.coalesce(column, ""))
    return or_(lowered_location.like("%.html"), lowered_location.like("%.htm"))


def catalog_ids_for_city(
    services: SegmentSelectionServices,
    city: str,
    *,
    limit: int | None = None,
    resume_after_id: int | None = None,
) -> list[int]:
    aliases = sorted(services.source_aliases_for_city(city))
    with services.db_session() as session:
        rows = (
            session.query(Catalog.id)
            .join(Document, Catalog.id == Document.catalog_id)
            .join(Event, Document.event_id == Event.id)
            .outerjoin(AgendaItem, Catalog.id == AgendaItem.catalog_id)
            .filter(
                Document.category.in_(("agenda", "agenda_html")),
                Catalog.content.is_not(None),
                Catalog.content != "",
                Event.source.in_(aliases),
                Catalog.id > resume_after_id if resume_after_id is not None else True,
                or_(
                    Catalog.agenda_segmentation_status == None,
                    Catalog.agenda_segmentation_status == "failed",
                    and_(
                        Catalog.agenda_segmentation_status == "complete",
                        AgendaItem.page_number == None,
                    ),
                ),
            )
            .distinct()
            .order_by(Catalog.id)
        )
        if limit is not None:
            rows = rows.limit(limit)
        selected_rows = rows.all()
    return [int(row[0]) for row in selected_rows]


def prioritized_catalog_ids(services: SegmentSelectionServices, city: str, catalog_ids: list[int]) -> list[int]:
    if not catalog_ids:
        return []
    aliases = sorted(services.source_aliases_for_city(city))
    with services.db_session() as session:
        rows = (
            session.query(Catalog.id, Catalog.location, Event.id)
            .join(Document, Catalog.id == Document.catalog_id)
            .join(Event, Document.event_id == Event.id)
            .filter(
                Catalog.id.in_(catalog_ids),
                Event.source.in_(aliases),
            )
            .all()
        )
        event_ids = sorted({int(row[2]) for row in rows})
        html_event_ids = {
            int(row[0])
            for row in session.query(Document.event_id)
            .join(Catalog, Catalog.id == Document.catalog_id)
            .join(Event, Document.event_id == Event.id)
            .filter(
                Document.event_id.in_(event_ids),
                Document.category == "agenda",
                Event.source.in_(aliases),
                html_location_predicate(Catalog.location),
            )
            .distinct()
            .all()
        }

    metadata_by_catalog_id = {
        int(catalog_id): {"location": location, "event_id": int(event_id)}
        for catalog_id, location, event_id in rows
    }
    return sorted((int(catalog_id) for catalog_id in catalog_ids), key=lambda catalog_id: _priority(catalog_id, metadata_by_catalog_id, html_event_ids))


def _priority(
    catalog_id: int,
    metadata_by_catalog_id: dict[int, dict[str, int | str | None]],
    html_event_ids: set[int],
) -> tuple[int, int]:
    metadata = metadata_by_catalog_id[int(catalog_id)]
    location = metadata["location"]
    if isinstance(location, str) and location.lower().endswith((".html", ".htm")):
        return (0, int(catalog_id))
    if int(metadata["event_id"] or 0) in html_event_ids:
        return (1, int(catalog_id))
    return (2, int(catalog_id))

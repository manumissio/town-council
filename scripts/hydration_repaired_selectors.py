from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import and_, or_

from pipeline.models import AgendaItem, Catalog, Document, Event


def selector_mode(url_substring: str | None) -> str:
    if url_substring:
        return f"url_substring:{url_substring}"
    return "city_agenda_repair"


def usable_local_artifact_status(location: str | None) -> str | None:
    if not location:
        return "missing_file"
    artifact_path = Path(location)
    if not artifact_path.exists():
        return "missing_file"
    if artifact_path.stat().st_size <= 0:
        return "zero_byte"
    return None


def apply_url_substring_filter(query: Any, url_substring: str | None) -> Any:
    if not url_substring:
        return query
    return query.filter(Catalog.url.ilike(f"%{url_substring}%"))


def select_extract_catalog_ids(
    *,
    db_session,
    source_aliases_for_city,
    artifact_status_checker,
    city: str,
    limit: int | None,
    resume_after_id: int | None,
    url_substring: str | None = None,
) -> tuple[list[int], dict[str, int]]:
    with db_session() as session:
        query = (
            session.query(Catalog.id, Catalog.location)
            .join(Document, Document.catalog_id == Catalog.id)
            .join(Event, Document.event_id == Event.id)
            .filter(
                Event.source.in_(sorted(source_aliases_for_city(city))),
                Document.category == "agenda",
                Catalog.summary.is_(None),
                Catalog.content.is_(None),
            )
            .order_by(Catalog.id)
        )
        query = apply_url_substring_filter(query, url_substring)
        if resume_after_id is not None:
            query = query.filter(Catalog.id > resume_after_id)
        rows = query.order_by(Catalog.id).all()

    counts = {"missing_file": 0, "zero_byte": 0}
    selected_ids: list[int] = []
    for catalog_id, location in rows:
        invalid_status = artifact_status_checker(location)
        if invalid_status:
            counts[invalid_status] += 1
            continue
        selected_ids.append(catalog_id)
        if limit is not None and len(selected_ids) >= limit:
            break
    return selected_ids, counts


def select_segment_catalog_ids(
    *,
    db_session,
    source_aliases_for_city,
    city: str,
    limit: int | None,
    resume_after_id: int | None,
    catalog_ids: list[int] | None = None,
    url_substring: str | None = None,
) -> list[int]:
    with db_session() as session:
        query = (
            session.query(Catalog.id)
            .join(Document, Document.catalog_id == Catalog.id)
            .join(Event, Document.event_id == Event.id)
            .outerjoin(AgendaItem, AgendaItem.catalog_id == Catalog.id)
            .filter(
                Event.source.in_(sorted(source_aliases_for_city(city))),
                Document.category == "agenda",
                Catalog.summary.is_(None),
                Catalog.content.is_not(None),
                Catalog.content != "",
                or_(
                    Catalog.agenda_segmentation_status.is_(None),
                    Catalog.agenda_segmentation_status == "failed",
                    and_(
                        Catalog.agenda_segmentation_status == "complete",
                        AgendaItem.page_number.is_(None),
                    ),
                ),
            )
            .distinct()
            .order_by(Catalog.id)
        )
        return _selected_catalog_ids(query, limit, resume_after_id, catalog_ids, url_substring)


def select_summary_catalog_ids(
    *,
    db_session,
    source_aliases_for_city,
    city: str,
    limit: int | None,
    resume_after_id: int | None,
    catalog_ids: list[int] | None = None,
    url_substring: str | None = None,
) -> list[int]:
    with db_session() as session:
        query = (
            session.query(Catalog.id)
            .join(Document, Document.catalog_id == Catalog.id)
            .join(Event, Document.event_id == Event.id)
            .join(AgendaItem, AgendaItem.catalog_id == Catalog.id)
            .filter(
                Event.source.in_(sorted(source_aliases_for_city(city))),
                Document.category == "agenda",
                Catalog.summary.is_(None),
                Catalog.content.is_not(None),
            )
            .distinct()
            .order_by(Catalog.id)
        )
        return _selected_catalog_ids(query, limit, resume_after_id, catalog_ids, url_substring)


def _selected_catalog_ids(
    query: Any,
    limit: int | None,
    resume_after_id: int | None,
    catalog_ids: list[int] | None,
    url_substring: str | None,
) -> list[int]:
    query = apply_url_substring_filter(query, url_substring)
    if catalog_ids is not None:
        if not catalog_ids:
            return []
        query = query.filter(Catalog.id.in_(catalog_ids))
    if resume_after_id is not None:
        query = query.filter(Catalog.id > resume_after_id)
    if limit is not None:
        query = query.limit(limit)
    return [row[0] for row in query.all()]

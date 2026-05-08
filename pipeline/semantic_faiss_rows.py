from __future__ import annotations

from typing import Any

from pipeline.models import AgendaItem, Catalog, Document, Event, Organization, Place
from pipeline.semantic_text import _build_chunks_from_content, _safe_text, catalog_semantic_text


def _semantic_index_facade():
    from pipeline import semantic_index

    return semantic_index


def _catalog_agenda_items(db) -> dict[int, list[AgendaItem]]:
    agenda_items_by_catalog: dict[int, list[AgendaItem]] = {}
    for agenda_item in (
        db.query(AgendaItem)
        .filter(AgendaItem.catalog_id.isnot(None))
        .order_by(AgendaItem.catalog_id, AgendaItem.order)
        .all()
    ):
        agenda_items_by_catalog.setdefault(int(agenda_item.catalog_id), []).append(agenda_item)
    return agenda_items_by_catalog


def _meeting_query(db):
    return (
        db.query(Document, Catalog, Event, Place, Organization)
        .join(Catalog, Document.catalog_id == Catalog.id)
        .join(Event, Document.event_id == Event.id)
        .join(Place, Document.place_id == Place.id)
        .outerjoin(Organization, Event.organization_id == Organization.id)
        .yield_per(50)
    )


def _base_metadata(catalog, event, place, org) -> dict[str, Any]:
    return {
        "catalog_id": catalog.id,
        "event_id": event.id,
        "date": event.record_date.isoformat() if event.record_date else None,
        "city": (place.display_name or place.name or "").lower(),
        "meeting_category": event.meeting_type or "Other",
        "organization": org.name if org else "City Council",
    }


def _append_summary_or_content_rows(texts, rows, counts, doc, catalog, event, base_meta, agenda_items) -> None:
    semantic_index = _semantic_index_facade()
    summary = catalog_semantic_text(catalog.summary)
    extractive = _safe_text(catalog.summary_extractive)
    if summary:
        texts.append(summary)
        rows.append(
            {"result_type": "meeting", "db_id": doc.id, "event_id": event.id, "source_type": "summary", **base_meta}
        )
        counts["summary"] += 1
    elif extractive:
        texts.append(extractive[: semantic_index.SEMANTIC_CONTENT_MAX_CHARS])
        rows.append(
            {
                "result_type": "meeting",
                "db_id": doc.id,
                "event_id": event.id,
                "source_type": "summary_extractive",
                **base_meta,
            }
        )
        counts["summary"] += 1
    elif agenda_items:
        _append_meeting_agenda_rows(texts, rows, counts, doc, event, base_meta, agenda_items)
    else:
        _append_content_chunk_rows(texts, rows, counts, doc, catalog, event, base_meta)


def _append_meeting_agenda_rows(texts, rows, counts, doc, event, base_meta, agenda_items) -> None:
    semantic_index = _semantic_index_facade()
    for agenda_item in agenda_items:
        chunk = _safe_text(f"{agenda_item.title or ''}. {agenda_item.description or ''}")
        if len(chunk) < 20:
            continue
        texts.append(chunk[: semantic_index.SEMANTIC_CONTENT_MAX_CHARS])
        rows.append(
            {
                "result_type": "meeting",
                "db_id": doc.id,
                "event_id": event.id,
                "source_type": "agenda_item",
                "agenda_item_id": agenda_item.id,
                **base_meta,
            }
        )
        counts["agenda_item"] += 1


def _append_content_chunk_rows(texts, rows, counts, doc, catalog, event, base_meta) -> None:
    semantic_index = _semantic_index_facade()
    for chunk in _build_chunks_from_content(catalog.content or "", semantic_index.SEMANTIC_CONTENT_MAX_CHARS):
        if len(chunk) < 20:
            continue
        texts.append(chunk)
        rows.append(
            {
                "result_type": "meeting",
                "db_id": doc.id,
                "event_id": event.id,
                "source_type": "content_chunk",
                **base_meta,
            }
        )
        counts["content_chunk"] += 1


def _append_agenda_item_result_rows(texts, rows, counts, event, base_meta, agenda_items) -> None:
    semantic_index = _semantic_index_facade()
    for agenda_item in agenda_items:
        item_text = _safe_text(f"{agenda_item.title or ''}. {agenda_item.description or ''}")
        if len(item_text) < 20:
            continue
        texts.append(item_text[: semantic_index.SEMANTIC_CONTENT_MAX_CHARS])
        rows.append(
            {
                "result_type": "agenda_item",
                "db_id": agenda_item.id,
                "event_id": event.id,
                "source_type": "agenda_item_result",
                **base_meta,
            }
        )
        counts["agenda_item_result"] += 1


def _collect_rows(backend, db) -> tuple[list[str], list[dict[str, Any]], dict[str, int]]:
    texts: list[str] = []
    rows: list[dict[str, Any]] = []
    counts = {"summary": 0, "agenda_item": 0, "content_chunk": 0, "agenda_item_result": 0}
    agenda_items_by_catalog = _catalog_agenda_items(db)

    for doc, catalog, event, place, org in _meeting_query(db):
        base_meta = _base_metadata(catalog, event, place, org)
        agenda_items = agenda_items_by_catalog.get(int(catalog.id), [])
        _append_summary_or_content_rows(texts, rows, counts, doc, catalog, event, base_meta, agenda_items)
        _append_agenda_item_result_rows(texts, rows, counts, event, base_meta, agenda_items)

    for row_id, row in enumerate(rows):
        row["row_id"] = row_id
    return texts, rows, counts

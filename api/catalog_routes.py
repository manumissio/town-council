from typing import Any, Callable

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session as SQLAlchemySession

from pipeline.content_hash import compute_content_hash
from pipeline.document_kinds import normalize_summary_doc_kind
from pipeline.models import AgendaItem, Catalog, Document, Event, Place
from pipeline.summary_freshness import compute_agenda_items_hash, is_summary_stale
from pipeline.summary_quality import (
    analyze_source_text,
    build_low_signal_message,
    is_source_summarizable,
    is_source_topicable,
)

BATCH_REQUEST_LIMIT = 50
BATCH_REQUEST_TOO_LARGE_DETAIL = "Batch request too large. Limit is 50 IDs."
DOCUMENT_NOT_FOUND_DETAIL = "Document not found"
PAGE_MARKER_PREFIX = "[PAGE "
VALID_AGENDA_SEGMENTATION_STATUSES = {None, "complete", "empty", "failed"}


def _summary_doc_kind_and_hashes(
    db: SQLAlchemySession,
    catalog_id: int,
    catalog: Catalog,
) -> tuple[str, str | None, str | None]:
    doc = db.query(Document).filter_by(catalog_id=catalog_id).first()
    doc_kind = normalize_summary_doc_kind(doc.category if doc else "unknown")
    content_hash = catalog.content_hash or (compute_content_hash(catalog.content) if catalog.content else None)
    agenda_items_hash = catalog.agenda_items_hash
    if doc_kind == "agenda":
        agenda_items = (
            db.query(AgendaItem)
            .filter_by(catalog_id=catalog_id)
            .order_by(AgendaItem.order)
            .all()
        )
        agenda_items_hash = compute_agenda_items_hash(agenda_items)
    return doc_kind, content_hash, agenda_items_hash


def build_catalog_router(
    get_db_dependency: Callable[..., Any],
    verify_api_key_dependency: Callable[..., Any],
) -> APIRouter:
    router = APIRouter()

    @router.get("/catalog/batch")
    def get_catalogs_batch(
        ids: list[int] = Query(...),
        db: SQLAlchemySession = Depends(get_db_dependency),
    ) -> list[dict[str, Any]]:
        """
        Returns a list of meeting summaries for multiple IDs.
        Used to display 'Related Meetings' links.
        """
        # Keep fanout bounded because this endpoint can be called from public UI links.
        if len(ids) > BATCH_REQUEST_LIMIT:
            raise HTTPException(status_code=400, detail=BATCH_REQUEST_TOO_LARGE_DETAIL)

        records = (
            db.query(Catalog, Document, Event, Place)
            .join(Document, Document.catalog_id == Catalog.id)
            .join(Event, Document.event_id == Event.id)
            .join(Place, Document.place_id == Place.id)
            .filter(Catalog.id.in_(ids))
            .all()
        )

        catalog_summaries = []
        for catalog, _doc, event, place in records:
            catalog_summaries.append(
                {
                    "id": catalog.id,
                    "filename": catalog.filename,
                    "title": event.name,
                    "date": event.record_date.isoformat() if event.record_date else None,
                    "city": place.display_name or place.name,
                }
            )
        return catalog_summaries

    @router.get("/catalog/{catalog_id}/content", dependencies=[Depends(verify_api_key_dependency)])
    def get_catalog_content(
        catalog_id: int = Path(..., ge=1),
        db: SQLAlchemySession = Depends(get_db_dependency),
    ) -> dict[str, Any]:
        """
        Return the raw extracted text for one catalog.

        This is primarily used by the UI after a re-extraction so the user can see
        updated text immediately (even before search reindexing completes).
        """
        catalog = db.get(Catalog, catalog_id)
        if not catalog:
            raise HTTPException(status_code=404, detail=DOCUMENT_NOT_FOUND_DETAIL)
        if not catalog.content:
            return {"catalog_id": catalog_id, "chars": 0, "content": ""}
        return {
            "catalog_id": catalog_id,
            "chars": len(catalog.content),
            "has_page_markers": PAGE_MARKER_PREFIX in catalog.content,
            "content": catalog.content,
        }

    @router.get("/catalog/{catalog_id}/derived_status", dependencies=[Depends(verify_api_key_dependency)])
    def get_catalog_derived_status(
        catalog_id: int = Path(..., ge=1),
        db: SQLAlchemySession = Depends(get_db_dependency),
    ) -> dict[str, Any]:
        """
        Return whether derived fields (summary/topics) are stale for the current extracted text.

        This endpoint is used by the UI to show a clear "stale" badge after re-extraction,
        without auto-regenerating anything.
        """
        catalog = db.get(Catalog, catalog_id)
        if not catalog:
            raise HTTPException(status_code=404, detail=DOCUMENT_NOT_FOUND_DETAIL)

        doc_kind, content_hash, agenda_items_hash = _summary_doc_kind_and_hashes(db, catalog_id, catalog)
        summary_is_stale = is_summary_stale(
            doc_kind,
            summary=catalog.summary,
            summary_source_hash=catalog.summary_source_hash,
            content_hash=content_hash,
            agenda_items_hash=agenda_items_hash,
        )
        topics_is_stale = bool(
            catalog.topics is not None and (not content_hash or catalog.topics_source_hash != content_hash)
        )
        agenda_segmentation_status = getattr(catalog, "agenda_segmentation_status", None)
        agenda_segmentation_attempted_at = getattr(catalog, "agenda_segmentation_attempted_at", None)
        agenda_segmentation_item_count = getattr(catalog, "agenda_segmentation_item_count", None)
        agenda_segmentation_error = getattr(catalog, "agenda_segmentation_error", None)

        if agenda_segmentation_status not in VALID_AGENDA_SEGMENTATION_STATUSES:
            agenda_segmentation_status = None

        # Prefer the catalog-level count if present; otherwise derive it from the current rows.
        if isinstance(agenda_segmentation_item_count, int):
            agenda_items_count = agenda_segmentation_item_count
        else:
            agenda_items_count = db.query(AgendaItem).filter(AgendaItem.catalog_id == catalog_id).count()
        quality = analyze_source_text(catalog.content or "")
        summary_blocked_reason = None
        topics_blocked_reason = None
        has_content = bool(catalog.content and catalog.content.strip())
        if has_content:
            if not is_source_summarizable(quality):
                summary_blocked_reason = build_low_signal_message(quality)
            if not is_source_topicable(quality):
                topics_blocked_reason = build_low_signal_message(quality)

        has_topics = catalog.topics is not None
        has_topic_values = bool(catalog.topics is not None and len(catalog.topics or []) > 0)
        summary_not_generated_yet = bool(has_content and not catalog.summary and not summary_blocked_reason)
        topics_not_generated_yet = bool(has_content and not has_topic_values and not topics_blocked_reason)
        # Agenda segmentation is separate: "not generated yet" means never attempted, while "empty" means attempted.
        agenda_not_generated_yet = bool(has_content and agenda_segmentation_status is None)
        agenda_is_empty = bool(has_content and agenda_segmentation_status == "empty")

        return {
            "catalog_id": catalog_id,
            "has_content": has_content,
            "content_hash": content_hash,
            "has_summary": bool(catalog.summary),
            "summary_source_hash": catalog.summary_source_hash,
            "summary_is_stale": summary_is_stale,
            "summary_blocked_reason": summary_blocked_reason,
            "summary_not_generated_yet": summary_not_generated_yet,
            "has_topics": has_topics,
            "topics_source_hash": catalog.topics_source_hash,
            "topics_is_stale": topics_is_stale,
            "topics_blocked_reason": topics_blocked_reason,
            "topics_not_generated_yet": topics_not_generated_yet,
            "agenda_items_count": agenda_items_count,
            "agenda_not_generated_yet": agenda_not_generated_yet,
            "agenda_is_empty": agenda_is_empty,
            "agenda_segmentation_status": agenda_segmentation_status,
            "agenda_segmentation_attempted_at": (
                agenda_segmentation_attempted_at.isoformat() if agenda_segmentation_attempted_at else None
            ),
            "agenda_segmentation_item_count": agenda_segmentation_item_count,
            "agenda_segmentation_error": agenda_segmentation_error,
        }

    return router

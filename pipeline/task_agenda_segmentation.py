from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from pipeline.llm import LocalAI
from pipeline.models import AgendaItem, Catalog, Document
from pipeline.task_runtime import logger
from pipeline.task_side_effects import REINDEX_FAILURE_EXCEPTIONS


SEGMENTATION_FAILED_STATUS = "failed"
SEGMENTATION_COMPLETE_STATUS = "complete"
SEGMENTATION_EMPTY_STATUS = "empty"
SEGMENTATION_ERROR_PAYLOAD_STATUS = "error"
SEGMENTATION_FAILURE_ERROR_LIMIT = 500


@dataclass(frozen=True)
class AgendaSegmentationTaskServices:
    classify_catalog_bad_content: Callable[..., object]
    has_viable_structured_agenda_source: Callable[..., bool]
    resolve_agenda_items: Callable[..., dict[str, Any]]
    persist_agenda_items: Callable[..., list[AgendaItem]]
    run_vote_extraction_for_catalog: Callable[..., dict[str, Any]]
    reindex_catalog: Callable[[int], object]
    vote_extraction_enabled: bool


def record_agenda_segmentation_status(
    catalog: Catalog,
    *,
    status: str,
    item_count: int,
    error_message: str | None,
) -> None:
    """
    Keep segmentation status writes explicit without introducing a generic task-state helper.
    """
    catalog.agenda_segmentation_status = status
    catalog.agenda_segmentation_item_count = item_count
    catalog.agenda_segmentation_attempted_at = datetime.now(timezone.utc)
    catalog.agenda_segmentation_error = error_message


def _vote_extraction_disabled_payload() -> dict[str, Any]:
    return {
        "status": "disabled",
        "processed_items": 0,
        "updated_items": 0,
        "skipped_items": 0,
        "failed_items": 0,
        "skip_reasons": {},
    }


def _vote_extraction_skipped_payload() -> dict[str, Any]:
    return {
        "status": "skipped_no_items",
        "processed_items": 0,
        "updated_items": 0,
        "skipped_items": 0,
        "failed_items": 0,
        "skip_reasons": {},
    }


def _vote_extraction_failed_payload(error_name: str) -> dict[str, Any]:
    return {
        "status": "failed",
        "error": error_name,
        "processed_items": 0,
        "updated_items": 0,
        "skipped_items": 0,
        "failed_items": 0,
        "skip_reasons": {},
    }


def run_post_segmentation_vote_extraction(
    db,
    *,
    local_ai: LocalAI,
    catalog: Catalog,
    doc: Document,
    created_items: list[AgendaItem],
    services: AgendaSegmentationTaskServices,
) -> dict[str, Any]:
    """
    Vote extraction remains a non-gating post-segmentation stage in this task family.
    """
    if not services.vote_extraction_enabled:
        return _vote_extraction_disabled_payload()

    try:
        vote_counters = services.run_vote_extraction_for_catalog(
            db,
            local_ai,
            catalog,
            doc,
            force=False,
            agenda_items=created_items,
        )
        return {"status": "complete", **vote_counters}
    except (RuntimeError, ValueError, KeyError) as vote_exc:
        logger.warning(
            "vote_extraction.post_segment_failed catalog_id=%s error=%s",
            catalog.id,
            vote_exc.__class__.__name__,
        )
        return _vote_extraction_failed_payload(vote_exc.__class__.__name__)


def persist_agenda_segmentation_failure_status(
    db,
    catalog_id: int,
    error_message: str,
) -> None:
    """
    Failure persistence is best-effort and stays under task-wrapper ownership.
    """
    catalog = db.get(Catalog, catalog_id)
    if not catalog:
        return
    record_agenda_segmentation_status(
        catalog,
        status=SEGMENTATION_FAILED_STATUS,
        item_count=0,
        error_message=error_message[:SEGMENTATION_FAILURE_ERROR_LIMIT],
    )
    db.commit()


def _agenda_items_payload(created_items: list[AgendaItem], source_used: str) -> list[dict[str, Any]]:
    return [
        {
            "title": item.title,
            "description": item.description,
            "order": item.order,
            "classification": item.classification,
            "result": item.result,
            "page_number": item.page_number,
            "source": source_used,
        }
        for item in created_items
    ]


def run_segment_agenda_task_family(
    db,
    catalog_id: int,
    *,
    local_ai: LocalAI,
    services: AgendaSegmentationTaskServices,
) -> dict[str, Any]:
    """
    Run agenda segmentation for one catalog while leaving retries and failure persistence to the task.
    """
    catalog = db.get(Catalog, catalog_id)

    if not catalog or not catalog.content:
        return {"error": "No content"}

    doc = db.query(Document).filter_by(catalog_id=catalog_id).first()
    if not doc:
        return {"error": "Document not linked to event"}

    classification = services.classify_catalog_bad_content(
        catalog,
        document_category=getattr(doc, "category", None),
        include_document_shape=True,
        has_viable_structured_source=services.has_viable_structured_agenda_source(db, catalog, doc),
    )
    if classification:
        record_agenda_segmentation_status(
            catalog,
            status=SEGMENTATION_FAILED_STATUS,
            item_count=0,
            error_message=classification.reason,
        )
        db.commit()
        return {"status": SEGMENTATION_ERROR_PAYLOAD_STATUS, "error": classification.reason}

    resolved = services.resolve_agenda_items(db, catalog, doc, local_ai)
    items_data = resolved["items"]

    item_count = 0
    items_to_return = []
    if items_data:
        created_items = services.persist_agenda_items(db, catalog_id, doc.event_id, items_data)
        items_to_return = _agenda_items_payload(created_items, resolved["source_used"])
        item_count = len(items_to_return)
        vote_extraction = run_post_segmentation_vote_extraction(
            db,
            local_ai=local_ai,
            catalog=catalog,
            doc=doc,
            created_items=created_items,
            services=services,
        )
        record_agenda_segmentation_status(
            catalog,
            status=SEGMENTATION_COMPLETE_STATUS,
            item_count=item_count,
            error_message=None,
        )
        db.commit()
        try:
            services.reindex_catalog(catalog_id)
        except REINDEX_FAILURE_EXCEPTIONS as reindex_error:
            # Agenda items are already persisted, so targeted reindex remains best-effort.
            logger.warning("agenda_segmentation.reindex_failed catalog_id=%s error=%s", catalog_id, reindex_error)
    else:
        record_agenda_segmentation_status(
            catalog,
            status=SEGMENTATION_EMPTY_STATUS,
            item_count=0,
            error_message=None,
        )
        db.commit()
        vote_extraction = _vote_extraction_skipped_payload()

    logger.info("Segmentation complete: %s items found (source=%s)", item_count, resolved["source_used"])
    return {
        "status": "complete",
        "item_count": item_count,
        "items": items_to_return,
        "source_used": resolved["source_used"],
        "quality_score": resolved["quality_score"],
        "vote_extraction": vote_extraction,
    }

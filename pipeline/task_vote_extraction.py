from collections.abc import Callable
from typing import Any

from pipeline.llm import LocalAI
from pipeline.models import AgendaItem, Catalog, Document
from pipeline.task_runtime import logger
from pipeline.task_side_effects import REINDEX_FAILURE_EXCEPTIONS


def _vote_extraction_disabled_payload() -> dict[str, Any]:
    return {
        "status": "disabled",
        "reason": "Vote extraction is disabled. Set ENABLE_VOTE_EXTRACTION=true or run with force=true.",
        "processed_items": 0,
        "updated_items": 0,
        "skipped_items": 0,
        "failed_items": 0,
        "skip_reasons": {},
    }


def _vote_extraction_not_ready_payload() -> dict[str, Any]:
    return {
        "status": "not_generated_yet",
        "reason": "Vote extraction requires segmented agenda items. Run segmentation first.",
        "processed_items": 0,
        "updated_items": 0,
        "skipped_items": 0,
        "failed_items": 0,
        "skip_reasons": {},
    }


def run_extract_votes_task_family(
    db,
    catalog_id: int,
    *,
    force: bool,
    local_ai: LocalAI,
    vote_extraction_enabled: bool,
    run_vote_extraction_for_catalog_callable: Callable[..., dict[str, Any]],
    reindex_catalog_callable: Callable[[int], object],
) -> dict[str, Any]:
    """
    Run vote extraction for one catalog while leaving retries and session cleanup to the task.
    """
    catalog = db.get(Catalog, catalog_id)
    if not catalog:
        return {"error": "Catalog not found"}

    doc = db.query(Document).filter_by(catalog_id=catalog_id).first()
    if not doc:
        return {"error": "Document not linked to catalog"}

    if not vote_extraction_enabled and not force:
        return _vote_extraction_disabled_payload()

    existing_items = (
        db.query(AgendaItem)
        .filter_by(catalog_id=catalog_id)
        .order_by(AgendaItem.order)
        .all()
    )
    if not existing_items:
        return _vote_extraction_not_ready_payload()

    counters = run_vote_extraction_for_catalog_callable(
        db,
        local_ai,
        catalog,
        doc,
        force=force,
        agenda_items=existing_items,
    )
    db.commit()

    try:
        reindex_catalog_callable(catalog_id)
    except REINDEX_FAILURE_EXCEPTIONS as reindex_error:
        # Vote extraction updates are already persisted, so targeted reindex remains best-effort.
        logger.warning("summary_generation.reindex_failed catalog_id=%s error=%s", catalog_id, reindex_error)

    return {"status": "complete", **counters}

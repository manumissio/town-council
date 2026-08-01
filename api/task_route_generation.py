from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session as SQLAlchemySession

from api import task_dispatch
from pipeline import summary_quality
from pipeline.content_hash import compute_content_hash
from pipeline.models import Catalog

EXTRACT_CACHED_CONTENT_MIN_CHARS = 800


def extract_votes_request(
    *,
    db: SQLAlchemySession,
    catalog_id: int,
    force: bool,
) -> dict[str, str]:
    catalog = db.get(Catalog, catalog_id)
    if not catalog:
        raise HTTPException(status_code=404, detail="Document not found")

    task_id = task_dispatch.enqueue_task(
        task_dispatch.EXTRACT_VOTES_OPERATION_KEY,
        task_dispatch.EXTRACT_VOTES_TASK_NAME,
        catalog_id,
        force=force,
    )
    return {
        "status": "processing",
        "task_id": task_id,
        "poll_url": f"/tasks/{task_id}",
    }


def generate_topics_request(
    *,
    db: SQLAlchemySession,
    catalog_id: int,
    force: bool,
) -> dict[str, Any]:
    catalog = db.get(Catalog, catalog_id)
    if not catalog:
        raise HTTPException(status_code=404, detail="Document not found")
    if not catalog.content:
        raise HTTPException(status_code=400, detail="Document has no text to tag")

    quality = summary_quality.analyze_source_text(catalog.content)
    if not summary_quality.is_source_topicable(quality):
        return {
            "status": "blocked_low_signal",
            "reason": summary_quality.build_low_signal_message(quality),
            "topics": [],
        }

    content_hash = catalog.content_hash or (compute_content_hash(catalog.content) if catalog.content else None)
    is_fresh = bool(
        catalog.topics is not None
        and content_hash
        and catalog.topics_source_hash
        and catalog.topics_source_hash == content_hash
    )
    if (not force) and is_fresh:
        return {"status": "cached", "topics": catalog.topics or []}
    if (not force) and catalog.topics is not None and not is_fresh:
        return {"status": "stale", "topics": catalog.topics or []}

    task_id = task_dispatch.enqueue_task(
        task_dispatch.GENERATE_TOPICS_OPERATION_KEY,
        task_dispatch.GENERATE_TOPICS_TASK_NAME,
        catalog_id,
        force=force,
    )
    return {
        "status": "processing",
        "task_id": task_id,
        "poll_url": f"/tasks/{task_id}",
    }


def extract_catalog_text_request(
    *,
    db: SQLAlchemySession,
    catalog_id: int,
    force: bool,
    ocr_fallback: bool,
) -> dict[str, Any]:
    catalog = db.get(Catalog, catalog_id)
    if not catalog:
        raise HTTPException(status_code=404, detail="Document not found")

    if (not force) and catalog.content and len(catalog.content.strip()) >= EXTRACT_CACHED_CONTENT_MIN_CHARS:
        return {"status": "cached", "catalog_id": catalog_id, "chars": len(catalog.content)}

    task_id = task_dispatch.enqueue_task(
        task_dispatch.EXTRACT_TEXT_OPERATION_KEY,
        task_dispatch.EXTRACT_TEXT_TASK_NAME,
        catalog_id,
        force=force,
        ocr_fallback=ocr_fallback,
    )
    return {
        "status": "processing",
        "task_id": task_id,
        "poll_url": f"/tasks/{task_id}",
    }

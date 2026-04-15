import logging
import sys
import uuid
from typing import Any, Callable

from celery.result import AsyncResult as AsyncResult
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from kombu.exceptions import KombuError
from sqlalchemy.orm import Session as SQLAlchemySession

from pipeline.celery_app import app as celery_app
from pipeline.content_hash import compute_content_hash
from pipeline.models import AgendaItem, Catalog
from pipeline.summary_freshness import is_summary_fresh
from pipeline.summary_quality import (
    analyze_source_text,
    build_low_signal_message,
    is_source_summarizable,
    is_source_topicable,
)

logger = logging.getLogger("town-council-api")

API_MAIN_FACADE_MODULE = "api.main"
TASK_QUEUE_UNAVAILABLE_DETAIL = "Task queue unavailable"
INVALID_TASK_ID_DETAIL = "Invalid task_id format"
GENERATE_SUMMARY_TASK_NAME = "pipeline.tasks.generate_summary_task"
GENERATE_TOPICS_TASK_NAME = "pipeline.enrichment_tasks.generate_topics_task"
SEGMENT_AGENDA_TASK_NAME = "pipeline.tasks.segment_agenda_task"
EXTRACT_VOTES_TASK_NAME = "pipeline.tasks.extract_votes_task"
EXTRACT_TEXT_TASK_NAME = "pipeline.tasks.extract_text_task"
SUMMARIZE_RATE_LIMIT = "20/minute"
SEGMENT_RATE_LIMIT = "20/minute"
VOTES_RATE_LIMIT = "20/minute"
TOPICS_RATE_LIMIT = "10/minute"
EXTRACT_RATE_LIMIT = "5/minute"
EXTRACT_CACHED_CONTENT_MIN_CHARS = 800
TASK_DISPATCH_ERRORS = (KombuError, OSError, ConnectionError, TimeoutError)


class _CeleryTaskProxy:
    """
    Keep the API enqueue surface lightweight while preserving test patch points.
    """

    def __init__(self, task_name: str):
        self.name = task_name

    def delay(self, *args: Any, **kwargs: Any) -> Any:
        return celery_app.send_task(self.name, args=args, kwargs=kwargs)


generate_summary_task = _CeleryTaskProxy(GENERATE_SUMMARY_TASK_NAME)
generate_topics_task = _CeleryTaskProxy(GENERATE_TOPICS_TASK_NAME)
segment_agenda_task = _CeleryTaskProxy(SEGMENT_AGENDA_TASK_NAME)
extract_votes_task = _CeleryTaskProxy(EXTRACT_VOTES_TASK_NAME)
extract_text_task = _CeleryTaskProxy(EXTRACT_TEXT_TASK_NAME)


def _api_main_facade() -> Any:
    facade = sys.modules.get(API_MAIN_FACADE_MODULE)
    if facade is None:
        raise RuntimeError("api.main facade is not loaded")
    return facade


def _enqueue_task(task_name: str, task_callable: Any, *task_args: Any, **task_kwargs: Any) -> str:
    """
    Normalize broker/enqueue failures at the API boundary.

    Why this exists:
    The API can be healthy enough to answer /health while the Celery broker is
    degraded. In that case we want an explicit 503 instead of a generic 500 or
    a response body without task_id.
    """
    try:
        task = task_callable.delay(*task_args, **task_kwargs)
    except TASK_DISPATCH_ERRORS as exc:
        logger.error(
            "Task enqueue failed",
            extra={"task_name": task_name, "failure_class": exc.__class__.__name__},
            exc_info=True,
        )
        raise HTTPException(status_code=503, detail=TASK_QUEUE_UNAVAILABLE_DETAIL) from exc

    task_id = str(getattr(task, "id", "") or "").strip()
    if not task_id:
        logger.error(
            "Task enqueue returned missing task id",
            extra={"task_name": task_name, "failure_class": "missing_task_id"},
        )
        raise HTTPException(status_code=503, detail=TASK_QUEUE_UNAVAILABLE_DETAIL)
    return task_id


def build_task_router(
    limiter: Any,
    get_db_dependency: Callable[..., Any],
    verify_api_key_dependency: Callable[..., Any],
) -> APIRouter:
    router = APIRouter()

    @router.post("/summarize/{catalog_id}", dependencies=[Depends(verify_api_key_dependency)])
    @limiter.limit(SUMMARIZE_RATE_LIMIT)
    def summarize_document(
        request: Request,
        catalog_id: int = Path(..., ge=1),
        force: bool = Query(
            False,
            description=(
                "Force regeneration even if a cached summary exists. "
                "Useful after summarization logic changes or when cached data is known-bad."
            ),
        ),
        db: SQLAlchemySession = Depends(get_db_dependency),
    ) -> dict[str, Any]:
        """
        Async AI: Requests a summary generation.
        Returns a 'Task ID' immediately. Use GET /tasks/{id} to check progress.
        """
        _ = request
        catalog = db.get(Catalog, catalog_id)
        if not catalog:
            raise HTTPException(status_code=404, detail="Document not found")
        if not catalog.content:
            raise HTTPException(status_code=400, detail="Document has no text to summarize")

        # Block generation when extracted text is too weak to support reliable output.
        quality = analyze_source_text(catalog.content)
        if not is_source_summarizable(quality):
            return {
                "status": "blocked_low_signal",
                "reason": build_low_signal_message(quality),
            }

        facade = _api_main_facade()
        doc_kind, content_hash, agenda_items_hash = facade._summary_doc_kind_and_hashes(db, catalog_id, catalog)
        is_fresh = is_summary_fresh(
            doc_kind,
            summary=catalog.summary,
            summary_source_hash=catalog.summary_source_hash,
            content_hash=content_hash,
            agenda_items_hash=agenda_items_hash,
        )

        if (not force) and is_fresh:
            return {"summary": catalog.summary, "status": "cached"}
        if (not force) and catalog.summary and not is_fresh:
            return {"summary": catalog.summary, "status": "stale"}

        task_id = facade._enqueue_task(
            "generate_summary_task",
            facade.generate_summary_task,
            catalog_id,
            force=force,
        )
        return {
            "status": "processing",
            "task_id": task_id,
            "poll_url": f"/tasks/{task_id}",
        }

    @router.post("/segment/{catalog_id}", dependencies=[Depends(verify_api_key_dependency)])
    @limiter.limit(SEGMENT_RATE_LIMIT)
    def segment_agenda(
        request: Request,
        catalog_id: int = Path(..., ge=1),
        force: bool = Query(
            False,
            description=(
                "Force regeneration even if cached items exist. "
                "Useful after segmentation logic changes or when cached data is known-bad."
            ),
        ),
        db: SQLAlchemySession = Depends(get_db_dependency),
    ) -> dict[str, Any]:
        """
        Async AI: Requests agenda segmentation.
        Returns a 'Task ID' immediately.
        """
        _ = request
        catalog = db.get(Catalog, catalog_id)
        if not catalog:
            raise HTTPException(status_code=404, detail="Document not found")

        existing_items = db.query(AgendaItem).filter_by(catalog_id=catalog_id).order_by(AgendaItem.order).all()
        facade = _api_main_facade()
        if (
            not force
            and existing_items
            and facade.agenda_items_look_low_quality
            and not facade.agenda_items_look_low_quality(existing_items)
        ):
            return {"status": "cached", "items": existing_items}
        if not force and existing_items:
            logger.info(
                "Agenda cache for catalog_id=%s looks low quality; regenerating asynchronously.",
                catalog_id,
            )
        if force:
            logger.info("Force-regenerating agenda cache for catalog_id=%s.", catalog_id)

        task_id = facade._enqueue_task("segment_agenda_task", facade.segment_agenda_task, catalog_id)
        return {
            "status": "processing",
            "task_id": task_id,
            "poll_url": f"/tasks/{task_id}",
        }

    @router.post("/votes/{catalog_id}", dependencies=[Depends(verify_api_key_dependency)])
    @limiter.limit(VOTES_RATE_LIMIT)
    def extract_votes(
        request: Request,
        catalog_id: int = Path(..., ge=1),
        force: bool = Query(
            False,
            description=(
                "Force vote extraction even when the feature flag is disabled or items already have "
                "high-confidence LLM vote data."
            ),
        ),
        db: SQLAlchemySession = Depends(get_db_dependency),
    ) -> dict[str, str]:
        """
        Async AI: Requests vote/outcome extraction for segmented agenda items.
        Returns a Task ID immediately.
        """
        _ = request
        catalog = db.get(Catalog, catalog_id)
        if not catalog:
            raise HTTPException(status_code=404, detail="Document not found")

        facade = _api_main_facade()
        task_id = facade._enqueue_task("extract_votes_task", facade.extract_votes_task, catalog_id, force=force)
        return {
            "status": "processing",
            "task_id": task_id,
            "poll_url": f"/tasks/{task_id}",
        }

    @router.post("/topics/{catalog_id}", dependencies=[Depends(verify_api_key_dependency)])
    @limiter.limit(TOPICS_RATE_LIMIT)
    def generate_topics_for_catalog(
        request: Request,
        catalog_id: int = Path(..., ge=1),
        force: bool = Query(
            False,
            description=(
                "Force regeneration even if cached topics exist. "
                "Useful after extraction changes or when cached topics are known-bad."
            ),
        ),
        db: SQLAlchemySession = Depends(get_db_dependency),
    ) -> dict[str, Any]:
        """
        Async topic tagging: requests topic generation for one catalog.

        We keep regeneration explicit (no automatic re-tagging after extraction),
        but we also avoid serving "cached" topics when they are stale.
        """
        _ = request
        catalog = db.get(Catalog, catalog_id)
        if not catalog:
            raise HTTPException(status_code=404, detail="Document not found")
        if not catalog.content:
            raise HTTPException(status_code=400, detail="Document has no text to tag")

        quality = analyze_source_text(catalog.content)
        if not is_source_topicable(quality):
            return {
                "status": "blocked_low_signal",
                "reason": build_low_signal_message(quality),
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

        facade = _api_main_facade()
        task_id = facade._enqueue_task(
            "generate_topics_task",
            facade.generate_topics_task,
            catalog_id,
            force=force,
        )
        return {
            "status": "processing",
            "task_id": task_id,
            "poll_url": f"/tasks/{task_id}",
        }

    @router.post("/extract/{catalog_id}", dependencies=[Depends(verify_api_key_dependency)])
    @limiter.limit(EXTRACT_RATE_LIMIT)
    def extract_catalog_text(
        request: Request,
        catalog_id: int = Path(..., ge=1),
        force: bool = Query(
            False,
            description="Force re-extraction even if cached extracted text exists.",
        ),
        ocr_fallback: bool = Query(
            False,
            description="Allow OCR fallback when the PDF has little/no selectable text (slower).",
        ),
        db: SQLAlchemySession = Depends(get_db_dependency),
    ) -> dict[str, Any]:
        """
        Async extraction: re-extract one catalog's text from its already-downloaded file.

        We do not download here. If the file isn't present on disk, the task fails fast.
        """
        _ = request
        catalog = db.get(Catalog, catalog_id)
        if not catalog:
            raise HTTPException(status_code=404, detail="Document not found")

        if (not force) and catalog.content and len(catalog.content.strip()) >= EXTRACT_CACHED_CONTENT_MIN_CHARS:
            return {"status": "cached", "catalog_id": catalog_id, "chars": len(catalog.content)}

        facade = _api_main_facade()
        task_id = facade._enqueue_task(
            "extract_text_task",
            facade.extract_text_task,
            catalog_id,
            force=force,
            ocr_fallback=ocr_fallback,
        )
        return {
            "status": "processing",
            "task_id": task_id,
            "poll_url": f"/tasks/{task_id}",
        }

    @router.get("/tasks/{task_id}")
    def get_task_status(task_id: str) -> dict[str, Any]:
        """
        Check the status of a background AI task.
        """
        try:
            uuid.UUID(task_id)
        except (ValueError, TypeError):
            logger.warning("Invalid task status request", extra={"task_id": task_id})
            raise HTTPException(status_code=400, detail=INVALID_TASK_ID_DETAIL)

        facade = _api_main_facade()
        task = facade.AsyncResult(task_id, app=celery_app)
        if not task.ready():
            return {"status": "processing"}

        task_payload = task.result
        if isinstance(task_payload, Exception):
            return {"status": "failed", "error": str(task_payload)}
        if isinstance(task_payload, dict) and "error" in task_payload:
            return {"status": "failed", "error": task_payload["error"]}

        return {
            "status": "complete",
            "result": task_payload,
        }

    return router

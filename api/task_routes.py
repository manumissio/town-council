import logging
from typing import Any, Callable

from celery.result import AsyncResult as AsyncResult
from fastapi import APIRouter, Depends, Path, Query, Request
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
from api.task_dispatch import (  # noqa: F401
    EXTRACT_TEXT_TASK_NAME,
    EXTRACT_VOTES_TASK_NAME,
    GENERATE_SUMMARY_TASK_NAME,
    GENERATE_TOPICS_TASK_NAME,
    INVALID_TASK_ID_DETAIL,
    SEGMENT_AGENDA_TASK_NAME,
    TASK_DISPATCH_ERRORS,
    TASK_QUEUE_UNAVAILABLE_DETAIL,
    _CeleryTaskProxy,
    _enqueue_task,
    extract_text_task,
    extract_votes_task,
    generate_summary_task,
    generate_topics_task,
    segment_agenda_task,
)
from api.task_route_generation import (
    extract_catalog_text_request,
    extract_votes_request,
    generate_topics_request,
)
from api.task_route_segmentation import segment_agenda_request
from api.task_route_summary import summarize_document_request
from api.task_route_support import get_task_status_payload

logger = logging.getLogger("town-council-api")

SUMMARIZE_RATE_LIMIT = "20/minute"
SEGMENT_RATE_LIMIT = "20/minute"
VOTES_RATE_LIMIT = "20/minute"
TOPICS_RATE_LIMIT = "10/minute"
EXTRACT_RATE_LIMIT = "5/minute"
EXTRACT_CACHED_CONTENT_MIN_CHARS = 800


def build_task_router(
    limiter: Any,
    get_db_dependency: Callable[..., Any],
    verify_api_key_dependency: Callable[..., Any],
    task_facade: Any,
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
        return summarize_document_request(
            task_facade=task_facade,
            db=db,
            catalog_id=catalog_id,
            force=force,
            catalog_model=Catalog,
            analyze_source_text=analyze_source_text,
            build_low_signal_message=build_low_signal_message,
            is_summary_fresh=is_summary_fresh,
            is_source_summarizable=is_source_summarizable,
        )

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
        return segment_agenda_request(
            task_facade=task_facade,
            db=db,
            catalog_id=catalog_id,
            force=force,
            catalog_model=Catalog,
            agenda_item_model=AgendaItem,
            logger=logger,
        )

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
        return extract_votes_request(
            task_facade=task_facade,
            db=db,
            catalog_id=catalog_id,
            force=force,
            catalog_model=Catalog,
        )

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
        return generate_topics_request(
            task_facade=task_facade,
            db=db,
            catalog_id=catalog_id,
            force=force,
            catalog_model=Catalog,
            analyze_source_text=analyze_source_text,
            build_low_signal_message=build_low_signal_message,
            compute_content_hash=compute_content_hash,
            is_source_topicable=is_source_topicable,
        )

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
        return extract_catalog_text_request(
            task_facade=task_facade,
            db=db,
            catalog_id=catalog_id,
            force=force,
            ocr_fallback=ocr_fallback,
            catalog_model=Catalog,
            cached_content_min_chars=EXTRACT_CACHED_CONTENT_MIN_CHARS,
        )

    @router.get("/tasks/{task_id}")
    def get_task_status(task_id: str) -> dict[str, Any]:
        """
        Check the status of a background AI task.
        """
        return get_task_status_payload(task_facade, task_id, celery_app=celery_app, logger=logger)

    return router

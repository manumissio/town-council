from typing import Any, Callable

from fastapi import APIRouter, Depends, Path, Query, Request
from sqlalchemy.orm import Session as SQLAlchemySession

from api.task_route_generation import (
    extract_catalog_text_request,
    extract_votes_request,
    generate_topics_request,
)
from api.task_route_segmentation import segment_agenda_request
from api.task_route_summary import summarize_document_request
from api.task_route_support import get_task_status_payload

SUMMARIZE_RATE_LIMIT = "20/minute"
SEGMENT_RATE_LIMIT = "20/minute"
VOTES_RATE_LIMIT = "20/minute"
TOPICS_RATE_LIMIT = "10/minute"
EXTRACT_RATE_LIMIT = "5/minute"


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
        return summarize_document_request(
            db=db,
            catalog_id=catalog_id,
            force=force,
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
            db=db,
            catalog_id=catalog_id,
            force=force,
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
            db=db,
            catalog_id=catalog_id,
            force=force,
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
            db=db,
            catalog_id=catalog_id,
            force=force,
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
            db=db,
            catalog_id=catalog_id,
            force=force,
            ocr_fallback=ocr_fallback,
        )

    @router.get("/tasks/{task_id}")
    def get_task_status(task_id: str) -> dict[str, Any]:
        """
        Check the status of a background AI task.
        """
        return get_task_status_payload(task_id)

    return router

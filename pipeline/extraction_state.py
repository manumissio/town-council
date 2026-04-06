from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol

from pipeline.config import EXTRACTION_TERMINAL_FAILURE_MAX_ATTEMPTS


DEFAULT_EXTRACTION_ERROR_MESSAGE = "Extraction returned empty text"
EXTRACTION_COMPLETE_STATUS = "complete"
EXTRACTION_PENDING_STATUS = "pending"
EXTRACTION_FAILED_TERMINAL_STATUS = "failed_terminal"
EXTRACTION_ERROR_MESSAGE_LIMIT = 500


class ExtractionCatalogLike(Protocol):
    content_hash: str | None
    extraction_status: str | None
    extraction_attempt_count: int | None
    extraction_attempted_at: datetime | None
    extraction_error: str | None


def utc_now() -> datetime:
    """Use one shared UTC timestamp policy for extraction freshness fields."""
    return datetime.now(timezone.utc)


def mark_extraction_complete(catalog: ExtractionCatalogLike, content_hash: str | None) -> None:
    """Centralize extraction success bookkeeping so batch and retry paths stay aligned."""
    catalog.content_hash = content_hash
    catalog.extraction_status = EXTRACTION_COMPLETE_STATUS
    catalog.extraction_attempt_count = max(1, int(catalog.extraction_attempt_count or 0))
    catalog.extraction_attempted_at = utc_now()
    catalog.extraction_error = None


def mark_extraction_failure(catalog: ExtractionCatalogLike, error_message: str) -> None:
    """Keep failure-state transitions identical across all extraction entrypoints."""
    attempts = int(getattr(catalog, "extraction_attempt_count", 0) or 0) + 1
    catalog.extraction_attempt_count = attempts
    catalog.extraction_attempted_at = utc_now()
    catalog.extraction_error = (error_message or DEFAULT_EXTRACTION_ERROR_MESSAGE)[:EXTRACTION_ERROR_MESSAGE_LIMIT]
    catalog.extraction_status = (
        EXTRACTION_FAILED_TERMINAL_STATUS
        if attempts >= EXTRACTION_TERMINAL_FAILURE_MAX_ATTEMPTS
        else EXTRACTION_PENDING_STATUS
    )

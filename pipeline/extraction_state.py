from datetime import datetime, timezone

from pipeline.config import EXTRACTION_TERMINAL_FAILURE_MAX_ATTEMPTS


def utc_now():
    """Use one shared UTC timestamp policy for extraction freshness fields."""
    return datetime.now(timezone.utc)


def mark_extraction_complete(catalog, content_hash):
    """Centralize extraction success bookkeeping so batch and retry paths stay aligned."""
    catalog.content_hash = content_hash
    catalog.extraction_status = "complete"
    catalog.extraction_attempt_count = max(1, int(catalog.extraction_attempt_count or 0))
    catalog.extraction_attempted_at = utc_now()
    catalog.extraction_error = None


def mark_extraction_failure(catalog, error_message: str) -> None:
    """Keep failure-state transitions identical across all extraction entrypoints."""
    attempts = int(getattr(catalog, "extraction_attempt_count", 0) or 0) + 1
    catalog.extraction_attempt_count = attempts
    catalog.extraction_attempted_at = utc_now()
    catalog.extraction_error = (error_message or "Extraction returned empty text")[:500]
    catalog.extraction_status = (
        "failed_terminal"
        if attempts >= EXTRACTION_TERMINAL_FAILURE_MAX_ATTEMPTS
        else "pending"
    )

import os
from datetime import datetime

from pipeline.extractor import extract_text, is_safe_path
from pipeline.content_hash import compute_content_hash
from pipeline.text_cleaning import postprocess_extracted_text
from pipeline.config import EXTRACTION_TERMINAL_FAILURE_MAX_ATTEMPTS


def looks_like_good_extracted_text(text: str, min_chars: int) -> bool:
    """
    Return True when extracted text is "good enough" that we should not re-extract by default.

    This is intentionally simple and property-based:
    - Enough characters to be useful.
    - Not all whitespace.
    """
    if not text:
        return False
    stripped = text.strip()
    if not stripped:
        return False
    return len(stripped) >= min_chars


def reextract_catalog_content(catalog, *, force: bool, ocr_fallback: bool, min_chars: int):
    """
    Re-extract text for one Catalog from an already-downloaded file on disk.

    We *do not* download files here. If the file isn't present, we return an error.
    """
    if not catalog:
        return {"error": "Catalog not found"}

    if force:
        catalog.extraction_status = "pending"
        catalog.extraction_error = None

    if not catalog.location or catalog.location == "placeholder":
        _mark_extraction_failure(catalog, "Catalog has no file location")
        return {"error": "Catalog has no file location"}

    if not is_safe_path(catalog.location):
        _mark_extraction_failure(catalog, "Unsafe file path")
        return {"error": "Unsafe file path"}

    if not os.path.exists(catalog.location):
        _mark_extraction_failure(catalog, "File not found on disk")
        return {"error": "File not found on disk"}

    if (not force) and looks_like_good_extracted_text(catalog.content, min_chars=min_chars):
        catalog.extraction_status = "complete"
        return {"status": "cached", "catalog_id": catalog.id, "chars": len(catalog.content or "")}

    new_text = extract_text(
        catalog.location,
        ocr_fallback_enabled=ocr_fallback,
        min_chars_threshold=min_chars,
    )
    if not new_text:
        _mark_extraction_failure(catalog, "Extraction returned empty text")
        return {"error": "Extraction returned empty text"}

    # Store a cleaned version of extracted text so downstream NLP isn't dominated by
    # extraction artifacts (for example spaced-letter ALLCAPS like "P R O C L...").
    catalog.content = postprocess_extracted_text(new_text)
    # Hash ties derived fields (summary/topics) to a specific extracted text version.
    catalog.content_hash = compute_content_hash(catalog.content)
    catalog.extraction_status = "complete"
    catalog.extraction_attempt_count = max(1, int(catalog.extraction_attempt_count or 0))
    catalog.extraction_attempted_at = datetime.utcnow()
    catalog.extraction_error = None
    return {
        "status": "updated",
        "catalog_id": catalog.id,
        "chars": len(catalog.content),
        "ocr_fallback": bool(ocr_fallback),
        "content_hash": catalog.content_hash,
    }


def _mark_extraction_failure(catalog, error_message: str) -> None:
    attempts = int(getattr(catalog, "extraction_attempt_count", 0) or 0) + 1
    catalog.extraction_attempt_count = attempts
    catalog.extraction_attempted_at = datetime.utcnow()
    catalog.extraction_error = (error_message or "Extraction returned empty text")[:500]
    catalog.extraction_status = (
        "failed_terminal"
        if attempts >= EXTRACTION_TERMINAL_FAILURE_MAX_ATTEMPTS
        else "pending"
    )

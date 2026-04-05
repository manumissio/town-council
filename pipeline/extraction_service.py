import os

from pipeline.extractor import extract_text, is_safe_path
from pipeline.content_hash import compute_content_hash
from pipeline.laserfiche_error_pages import (
    classify_text_bad_content,
)
from pipeline.text_cleaning import postprocess_extracted_text
from pipeline.extraction_state import mark_extraction_complete, mark_extraction_failure


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
        mark_extraction_failure(catalog, "Catalog has no file location")
        return {"error": "Catalog has no file location"}

    if not is_safe_path(catalog.location):
        mark_extraction_failure(catalog, "Unsafe file path")
        return {"error": "Unsafe file path"}

    if not os.path.exists(catalog.location):
        mark_extraction_failure(catalog, "File not found on disk")
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
        mark_extraction_failure(catalog, "Extraction returned empty text")
        return {"error": "Extraction returned empty text"}

    # Store a cleaned version of extracted text so downstream NLP isn't dominated by
    # extraction artifacts (for example spaced-letter ALLCAPS like "P R O C L...").
    cleaned_text = postprocess_extracted_text(new_text)
    classification = classify_text_bad_content(
        cleaned_text,
        location=catalog.location,
        url=getattr(catalog, "url", None),
    )
    if classification:
        mark_extraction_failure(catalog, classification.reason)
        return {"error": classification.reason}

    catalog.content = cleaned_text
    # Hash ties derived fields (summary/topics) to a specific extracted text version.
    mark_extraction_complete(catalog, compute_content_hash(catalog.content))
    return {
        "status": "updated",
        "catalog_id": catalog.id,
        "chars": len(catalog.content),
        "ocr_fallback": bool(ocr_fallback),
        "content_hash": catalog.content_hash,
    }

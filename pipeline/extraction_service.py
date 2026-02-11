import os

from pipeline.extractor import extract_text, is_safe_path
from pipeline.content_hash import compute_content_hash


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

    if not catalog.location or catalog.location == "placeholder":
        return {"error": "Catalog has no file location"}

    if not is_safe_path(catalog.location):
        return {"error": "Unsafe file path"}

    if not os.path.exists(catalog.location):
        return {"error": "File not found on disk"}

    if (not force) and looks_like_good_extracted_text(catalog.content, min_chars=min_chars):
        return {"status": "cached", "catalog_id": catalog.id, "chars": len(catalog.content or "")}

    new_text = extract_text(
        catalog.location,
        ocr_fallback_enabled=ocr_fallback,
        min_chars_threshold=min_chars,
    )
    if not new_text:
        return {"error": "Extraction returned empty text"}

    catalog.content = new_text
    # Hash ties derived fields (summary/topics) to a specific extracted text version.
    catalog.content_hash = compute_content_hash(new_text)
    return {
        "status": "updated",
        "catalog_id": catalog.id,
        "chars": len(new_text),
        "ocr_fallback": bool(ocr_fallback),
        "content_hash": catalog.content_hash,
    }

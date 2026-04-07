from __future__ import annotations

import os
from importlib import import_module
from typing import Final, Literal, Protocol, TypedDict

from pipeline.content_hash import compute_content_hash
from pipeline.extraction_state import (
    EXTRACTION_COMPLETE_STATUS,
    EXTRACTION_PENDING_STATUS,
    ExtractionCatalogLike,
    mark_extraction_complete,
    mark_extraction_failure,
)


CATALOG_NOT_FOUND_ERROR: Final = "Catalog not found"
CATALOG_MISSING_LOCATION_ERROR: Final = "Catalog has no file location"
UNSAFE_FILE_PATH_ERROR: Final = "Unsafe file path"
FILE_NOT_FOUND_ERROR: Final = "File not found on disk"
EMPTY_EXTRACTION_ERROR: Final = "Extraction returned empty text"
PLACEHOLDER_LOCATION: Final = "placeholder"
CACHED_EXTRACTION_STATUS: Final = "cached"
UPDATED_EXTRACTION_STATUS: Final = "updated"


class ExtractionCatalogTarget(ExtractionCatalogLike, Protocol):
    id: int | None
    location: str | None
    url: str | None
    content: str | None


class BadContentClassificationLike(Protocol):
    reason: str


class SafePathChecker(Protocol):
    def __call__(self, catalog_path: str) -> bool: ...


class TextExtractor(Protocol):
    def __call__(
        self,
        catalog_path: str,
        *,
        ocr_fallback_enabled: bool,
        min_chars_threshold: int,
    ) -> str | None: ...


class TextPostprocessor(Protocol):
    def __call__(self, extracted_text: str) -> str: ...


class BadContentClassifier(Protocol):
    def __call__(
        self,
        cleaned_text: str,
        *,
        location: str | None,
        url: str | None,
    ) -> BadContentClassificationLike | None: ...


class ExtractionErrorResult(TypedDict):
    error: str


class CachedExtractionResult(TypedDict):
    status: Literal["cached"]
    catalog_id: int | None
    chars: int


class UpdatedExtractionResult(TypedDict):
    status: Literal["updated"]
    catalog_id: int | None
    chars: int
    ocr_fallback: bool
    content_hash: str | None


ExtractionServiceResult = ExtractionErrorResult | CachedExtractionResult | UpdatedExtractionResult


def _error_result(error_message: str) -> ExtractionErrorResult:
    return {"error": error_message}


def _cached_result(catalog: ExtractionCatalogTarget) -> CachedExtractionResult:
    return {
        "status": CACHED_EXTRACTION_STATUS,
        "catalog_id": catalog.id,
        "chars": len(catalog.content or ""),
    }


def _updated_result(catalog: ExtractionCatalogTarget, *, ocr_fallback: bool) -> UpdatedExtractionResult:
    return {
        "status": UPDATED_EXTRACTION_STATUS,
        "catalog_id": catalog.id,
        "chars": len(catalog.content or ""),
        "ocr_fallback": bool(ocr_fallback),
        "content_hash": catalog.content_hash,
    }


def _classify_bad_content_reason(
    cleaned_text: str,
    *,
    location: str | None,
    url: str | None,
) -> str | None:
    # Keep the service dependent on a stable rejection reason instead of classifier internals.
    laserfiche_module = import_module("pipeline.laserfiche_error_pages")
    classify_text_bad_content: BadContentClassifier = laserfiche_module.classify_text_bad_content
    classification = classify_text_bad_content(
        cleaned_text,
        location=location,
        url=url,
    )
    return classification.reason if classification else None


def _is_safe_catalog_path(catalog_path: str) -> bool:
    extractor_module = import_module("pipeline.extractor")
    is_safe_path: SafePathChecker = extractor_module.is_safe_path
    return is_safe_path(catalog_path)


def _extract_catalog_text(catalog_path: str, *, ocr_fallback: bool, min_chars: int) -> str | None:
    extractor_module = import_module("pipeline.extractor")
    extract_text: TextExtractor = extractor_module.extract_text
    return extract_text(
        catalog_path,
        ocr_fallback_enabled=ocr_fallback,
        min_chars_threshold=min_chars,
    )


def _postprocess_catalog_text(extracted_text: str) -> str:
    text_cleaning_module = import_module("pipeline.text_cleaning")
    postprocess_extracted_text: TextPostprocessor = text_cleaning_module.postprocess_extracted_text
    return postprocess_extracted_text(extracted_text)


def looks_like_good_extracted_text(text: str | None, min_chars: int) -> bool:
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


def reextract_catalog_content(
    catalog: ExtractionCatalogTarget | None,
    *,
    force: bool,
    ocr_fallback: bool,
    min_chars: int,
) -> ExtractionServiceResult:
    """
    Re-extract text for one Catalog from an already-downloaded file on disk.

    We *do not* download files here. If the file isn't present, we return an error.
    """
    if not catalog:
        return _error_result(CATALOG_NOT_FOUND_ERROR)

    if force:
        catalog.extraction_status = EXTRACTION_PENDING_STATUS
        catalog.extraction_error = None

    if not catalog.location or catalog.location == PLACEHOLDER_LOCATION:
        mark_extraction_failure(catalog, CATALOG_MISSING_LOCATION_ERROR)
        return _error_result(CATALOG_MISSING_LOCATION_ERROR)

    if not _is_safe_catalog_path(catalog.location):
        mark_extraction_failure(catalog, UNSAFE_FILE_PATH_ERROR)
        return _error_result(UNSAFE_FILE_PATH_ERROR)

    if not os.path.exists(catalog.location):
        mark_extraction_failure(catalog, FILE_NOT_FOUND_ERROR)
        return _error_result(FILE_NOT_FOUND_ERROR)

    if (not force) and looks_like_good_extracted_text(catalog.content, min_chars=min_chars):
        catalog.extraction_status = EXTRACTION_COMPLETE_STATUS
        return _cached_result(catalog)

    new_text = _extract_catalog_text(
        catalog.location,
        ocr_fallback=ocr_fallback,
        min_chars=min_chars,
    )
    if not new_text:
        mark_extraction_failure(catalog, EMPTY_EXTRACTION_ERROR)
        return _error_result(EMPTY_EXTRACTION_ERROR)

    # Store a cleaned version of extracted text so downstream NLP isn't dominated by
    # extraction artifacts (for example spaced-letter ALLCAPS like "P R O C L...").
    cleaned_text = _postprocess_catalog_text(new_text)
    bad_content_reason = _classify_bad_content_reason(
        cleaned_text,
        location=catalog.location,
        url=catalog.url,
    )
    if bad_content_reason:
        mark_extraction_failure(catalog, bad_content_reason)
        return _error_result(bad_content_reason)

    catalog.content = cleaned_text
    # Hash ties derived fields (summary/topics) to a specific extracted text version.
    mark_extraction_complete(catalog, compute_content_hash(catalog.content))
    return _updated_result(catalog, ocr_fallback=ocr_fallback)

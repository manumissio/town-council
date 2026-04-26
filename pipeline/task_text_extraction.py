from collections.abc import Callable
from typing import Any

from pipeline.models import Catalog
from pipeline.task_side_effects import REINDEX_FAILURE_EXCEPTIONS


_TRANSIENT_TEXT_EXTRACTION_ERRORS = frozenset(
    {
        "extraction returned empty text",
    }
)


def _is_transient_text_extraction_error(error_message: str) -> bool:
    """
    Keep retry policy explicit for text extraction without hiding it in a generic wrapper.
    """
    return error_message.lower() in _TRANSIENT_TEXT_EXTRACTION_ERRORS


def run_extract_text_task_family(
    db,
    catalog_id: int,
    *,
    force: bool,
    ocr_fallback: bool,
    min_chars: int,
    reextract_catalog_content_callable: Callable[..., dict[str, Any]],
    reindex_catalog_callable: Callable[[int], object],
) -> dict[str, Any]:
    """
    Run the single-catalog text re-extraction flow while leaving retry ownership to the task.
    """
    catalog = db.get(Catalog, catalog_id)
    result = reextract_catalog_content_callable(
        catalog,
        force=force,
        ocr_fallback=ocr_fallback,
        min_chars=min_chars,
    )
    if "error" in result:
        error_message = str(result["error"])
        if _is_transient_text_extraction_error(error_message):
            raise RuntimeError(error_message)
        return result

    db.commit()

    # The DB write is already durable here, so targeted reindex stays best-effort.
    try:
        reindex_catalog_callable(catalog_id)
    except REINDEX_FAILURE_EXCEPTIONS as reindex_error:
        return {**result, "reindex_error": str(reindex_error)}

    return result

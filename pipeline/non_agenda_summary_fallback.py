from __future__ import annotations

import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pipeline.agenda_summary_contracts import AGENDA_SUMMARY_EMBED_DISPATCH_ERRORS
from pipeline.content_hash import compute_content_hash
from pipeline.db_session import db_session
from pipeline.document_kinds import normalize_summary_doc_kind
from pipeline.laserfiche_error_pages import classify_catalog_bad_content
from pipeline.models import Catalog, Document
from pipeline.summary_freshness import compute_summary_source_hash
from pipeline.summary_quality import analyze_source_text, build_low_signal_message, is_source_summarizable
from pipeline.task_side_effects import REINDEX_FAILURE_EXCEPTIONS
from pipeline.task_summary_generation_contracts import (
    SUMMARY_BLOCKED_LOW_SIGNAL_STATUS,
    SUMMARY_COMPLETE_STATUS,
    SUMMARY_ERROR_STATUS,
)

logger = logging.getLogger(__name__)

NON_AGENDA_FALLBACK_COMPLETION_MODE = "deterministic_fallback"
NON_AGENDA_FALLBACK_NOTE = (
    "Generation note: Deterministic fallback used because the local AI provider "
    "returned an empty summary response."
)
NON_AGENDA_FALLBACK_REASON = "empty_response"
_CATALOG_NOT_FOUND_ERROR = "Catalog not found"
_DOCUMENT_NOT_FOUND_ERROR = "Document not found"
_NO_CONTENT_ERROR = "No content to summarize"
_UNSUPPORTED_DOC_KIND_ERROR = "Non-agenda fallback only supports minutes documents"
_MAX_EXCERPT_CHARS = 240


@dataclass(frozen=True)
class NonAgendaFallbackPersistence:
    summary: str
    doc_kind: str
    changed: bool


def build_non_agenda_fallback_summary_text(*, document: Document | None, content: str | None) -> str:
    doc_label = _document_label(document)
    excerpt = _fallback_excerpt(content)
    return (
        f"BLUF: {doc_label} text is available, but the local AI provider returned "
        "an empty response before it could generate a model summary.\n"
        f"- Source excerpt: {excerpt}\n"
        "- Review the extracted minutes for the authoritative meeting details.\n"
        "- Regenerate this summary after the local provider/runtime issue is resolved.\n"
        f"{NON_AGENDA_FALLBACK_NOTE}"
    )


def build_deterministic_non_agenda_summary_payload(
    catalog_id: int,
    *,
    reindex_callback: Callable[[int], Any] | None = None,
    embed_callback: Callable[[int], Any] | None = None,
    session_factory: Callable[[], Any] = db_session,
) -> dict[str, Any]:
    with session_factory() as session:
        persistence = _build_and_persist_non_agenda_fallback(session, catalog_id)
        if isinstance(persistence, dict):
            return persistence

    logger.warning(
        "non_agenda_summary_fallback.used catalog_id=%s doc_kind=%s fallback_reason=%s summary_fallback_mode=%s",
        catalog_id,
        persistence.doc_kind,
        NON_AGENDA_FALLBACK_REASON,
        "deterministic",
    )
    side_effects = _run_fallback_side_effects(
        catalog_id,
        reindex_callback=reindex_callback,
        embed_callback=embed_callback,
    )
    return {
        "status": SUMMARY_COMPLETE_STATUS,
        "summary": persistence.summary,
        "completion_mode": NON_AGENDA_FALLBACK_COMPLETION_MODE,
        "changed": persistence.changed,
        **side_effects,
    }


def _build_and_persist_non_agenda_fallback(
    session: Any,
    catalog_id: int,
) -> NonAgendaFallbackPersistence | dict[str, Any]:
    catalog = session.get(Catalog, catalog_id)
    document = session.query(Document).filter_by(catalog_id=catalog_id).first()
    validation_payload = _non_agenda_fallback_validation_payload(catalog, document)
    if validation_payload is not None:
        return validation_payload

    if catalog is None or document is None:
        return {"status": SUMMARY_ERROR_STATUS, "error": _CATALOG_NOT_FOUND_ERROR}
    doc_kind = normalize_summary_doc_kind(document.category)
    fallback_summary = build_non_agenda_fallback_summary_text(document=document, content=catalog.content)
    persisted_summary = _persist_non_agenda_fallback_summary(
        catalog=catalog,
        summary=fallback_summary,
        doc_kind=doc_kind,
        content_hash=compute_content_hash(catalog.content),
    )
    session.commit()
    return NonAgendaFallbackPersistence(
        summary=fallback_summary,
        doc_kind=doc_kind,
        changed=bool(persisted_summary["changed"]),
    )


def _document_label(document: Document | None) -> str:
    if document is None:
        return "Non-agenda document"
    doc_kind = normalize_summary_doc_kind(document.category)
    return f"{doc_kind.title()} document"


def _fallback_excerpt(content: str | None) -> str:
    normalized = re.sub(r"\s+", " ", content or "").strip()
    if not normalized:
        return "No extracted text was available."
    if len(normalized) <= _MAX_EXCERPT_CHARS:
        return normalized
    return f"{normalized[:_MAX_EXCERPT_CHARS].rstrip()}..."


def _non_agenda_fallback_validation_payload(
    catalog: Catalog | None,
    document: Document | None,
) -> dict[str, Any] | None:
    if catalog is None:
        return {"status": SUMMARY_ERROR_STATUS, "error": _CATALOG_NOT_FOUND_ERROR}
    if document is None:
        return {"status": SUMMARY_ERROR_STATUS, "error": _DOCUMENT_NOT_FOUND_ERROR}
    if normalize_summary_doc_kind(document.category) != "minutes":
        return {"status": SUMMARY_ERROR_STATUS, "error": _UNSUPPORTED_DOC_KIND_ERROR}
    if not catalog.content:
        return {"error": _NO_CONTENT_ERROR}
    classification = classify_catalog_bad_content(catalog)
    if classification:
        return {"status": SUMMARY_ERROR_STATUS, "error": classification.reason}
    quality = analyze_source_text(catalog.content)
    if not is_source_summarizable(quality):
        return {
            "status": SUMMARY_BLOCKED_LOW_SIGNAL_STATUS,
            "reason": build_low_signal_message(quality),
            "summary": None,
        }
    return None


def _persist_non_agenda_fallback_summary(
    *,
    catalog: Catalog,
    summary: str,
    doc_kind: str,
    content_hash: str | None,
) -> dict[str, Any]:
    prior_summary = catalog.summary
    prior_summary_source_hash = catalog.summary_source_hash
    summary_source_hash = compute_summary_source_hash(
        doc_kind,
        content_hash=content_hash,
        agenda_items_hash=None,
    )
    catalog.summary = summary
    if content_hash:
        catalog.content_hash = content_hash
    if summary_source_hash:
        catalog.summary_source_hash = summary_source_hash
    return {
        "status": SUMMARY_COMPLETE_STATUS,
        "summary": summary,
        "changed": bool(prior_summary != summary or prior_summary_source_hash != summary_source_hash),
    }


def _run_fallback_side_effects(
    catalog_id: int,
    *,
    reindex_callback: Callable[[int], Any] | None,
    embed_callback: Callable[[int], Any] | None,
) -> dict[str, int]:
    reindexed, reindex_failed = _run_reindex_callback(reindex_callback, catalog_id)
    embed_enqueued, embed_dispatch_failed = _run_embed_callback(embed_callback, catalog_id)
    return {
        "reindexed": reindexed,
        "reindex_failed": reindex_failed,
        "embed_enqueued": embed_enqueued,
        "embed_dispatch_failed": embed_dispatch_failed,
    }


def _run_reindex_callback(callback: Callable[[int], Any] | None, catalog_id: int) -> tuple[int, int]:
    if callback is None:
        return 0, 0
    try:
        callback(catalog_id)
        return 1, 0
    except REINDEX_FAILURE_EXCEPTIONS as reindex_error:
        logger.warning("non_agenda_summary_fallback.reindex_failed catalog_id=%s error=%s", catalog_id, reindex_error)
        return 0, 1


def _run_embed_callback(callback: Callable[[int], Any] | None, catalog_id: int) -> tuple[int, int]:
    if callback is None:
        return 0, 0
    try:
        callback(catalog_id)
        return 1, 0
    except AGENDA_SUMMARY_EMBED_DISPATCH_ERRORS as dispatch_error:
        logger.warning(
            "non_agenda_summary_fallback.embed_dispatch_failed catalog_id=%s error=%s",
            catalog_id,
            dispatch_error,
        )
        return 0, 1

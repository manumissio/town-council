from __future__ import annotations

import logging
import re
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Callable

from sqlalchemy.exc import SQLAlchemyError

from pipeline import agenda_summary_maintenance as agenda_summary_maintenance_mod
from pipeline import llm as llm_mod
from pipeline import llm_provider as llm_provider_mod
from pipeline.agenda_resolver import has_viable_structured_agenda_source, resolve_agenda_items
from pipeline.agenda_service import persist_agenda_items
from pipeline.config import AGENDA_SUMMARY_MAX_INPUT_CHARS, AGENDA_SUMMARY_MIN_RESERVED_OUTPUT_CHARS
from pipeline.db_session import db_session
from pipeline.laserfiche_error_pages import classify_catalog_bad_content
from pipeline.models import Catalog, Document

AGENDA_SUMMARY_READY_STATUS = agenda_summary_maintenance_mod.AGENDA_SUMMARY_READY_STATUS
AGENDA_SUMMARY_SEGMENTATION_REQUIRED_REASON = (
    agenda_summary_maintenance_mod.AGENDA_SUMMARY_SEGMENTATION_REQUIRED_REASON
)
AGENDA_SUMMARY_BLOCKED_LOW_SIGNAL_REASON = (
    agenda_summary_maintenance_mod.AGENDA_SUMMARY_BLOCKED_LOW_SIGNAL_REASON
)
AGENDA_SUMMARY_CATALOG_NOT_FOUND_ERROR = agenda_summary_maintenance_mod.AGENDA_SUMMARY_CATALOG_NOT_FOUND_ERROR
AGENDA_SUMMARY_DOCUMENT_NOT_FOUND_ERROR = agenda_summary_maintenance_mod.AGENDA_SUMMARY_DOCUMENT_NOT_FOUND_ERROR
AGENDA_SUMMARY_BUNDLE_BUILD_MS = agenda_summary_maintenance_mod.AGENDA_SUMMARY_BUNDLE_BUILD_MS
AGENDA_SUMMARY_RENDER_MS = agenda_summary_maintenance_mod.AGENDA_SUMMARY_RENDER_MS
AGENDA_SUMMARY_PERSIST_MS = agenda_summary_maintenance_mod.AGENDA_SUMMARY_PERSIST_MS
AGENDA_SUMMARY_REINDEX_MS = agenda_summary_maintenance_mod.AGENDA_SUMMARY_REINDEX_MS
AGENDA_SUMMARY_EMBED_DISPATCH_MS = agenda_summary_maintenance_mod.AGENDA_SUMMARY_EMBED_DISPATCH_MS
AGENDA_SUMMARY_TIMING_KEYS = agenda_summary_maintenance_mod.AGENDA_SUMMARY_TIMING_KEYS


@contextmanager
def provider_timeout_override(*, segment_timeout_seconds: int | None = None, summary_timeout_seconds: int | None = None):
    if segment_timeout_seconds is None and summary_timeout_seconds is None:
        yield
        return

    previous_segment_timeout = llm_provider_mod.LOCAL_AI_HTTP_TIMEOUT_SEGMENT_SECONDS
    previous_summary_timeout = llm_provider_mod.LOCAL_AI_HTTP_TIMEOUT_SUMMARY_SECONDS
    previous_instance = llm_mod.LocalAI._instance
    previous_provider = getattr(previous_instance, "_provider", None) if previous_instance else None
    previous_backend = getattr(previous_instance, "_provider_backend", None) if previous_instance else None
    if segment_timeout_seconds is not None:
        llm_provider_mod.LOCAL_AI_HTTP_TIMEOUT_SEGMENT_SECONDS = int(segment_timeout_seconds)
    if summary_timeout_seconds is not None:
        llm_provider_mod.LOCAL_AI_HTTP_TIMEOUT_SUMMARY_SECONDS = int(summary_timeout_seconds)
    if previous_instance is not None:
        previous_instance._provider = None
        previous_instance._provider_backend = None
    try:
        yield
    finally:
        llm_provider_mod.LOCAL_AI_HTTP_TIMEOUT_SEGMENT_SECONDS = previous_segment_timeout
        llm_provider_mod.LOCAL_AI_HTTP_TIMEOUT_SUMMARY_SECONDS = previous_summary_timeout
        current_instance = llm_mod.LocalAI._instance
        if current_instance is not None:
            current_instance._provider = previous_provider
            current_instance._provider_backend = previous_backend


@contextmanager
def segment_timeout_override(timeout_seconds: int | None):
    if timeout_seconds is None:
        yield
        return
    with provider_timeout_override(segment_timeout_seconds=timeout_seconds):
        yield


@contextmanager
def summary_timeout_override(timeout_seconds: int | None):
    if timeout_seconds is None:
        yield
        return
    with provider_timeout_override(summary_timeout_seconds=timeout_seconds):
        yield


@contextmanager
def capture_agenda_fallback_events() -> dict[str, int]:
    logger = logging.getLogger("local-ai")
    counts: Counter[str] = Counter()

    class _CaptureHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            message = record.getMessage()
            if "AI Agenda Extraction failed:" not in message:
                return
            lowered = message.lower()
            if "timed out" in lowered:
                counts["timeout"] += 1
            elif "empty response payload" in lowered:
                counts["empty_response"] += 1

    handler = _CaptureHandler()
    logger.addHandler(handler)
    try:
        yield counts
    finally:
        logger.removeHandler(handler)


@contextmanager
def capture_summary_fallback_events() -> dict[str, int]:
    logger = logging.getLogger("local-ai")
    counts: Counter[str] = Counter()

    class _CaptureHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            message = record.getMessage()
            if "AI Agenda Items Summarization failed" not in message:
                return
            lowered = message.lower()
            if "timed out" in lowered:
                counts["timeout"] += 1
            if "unavailable" in lowered or "connection" in lowered:
                counts["unavailable"] += 1

    handler = _CaptureHandler()
    logger.addHandler(handler)
    try:
        yield counts
    finally:
        logger.removeHandler(handler)


def looks_structured_enough_for_heuristic_segmentation(text: str | None) -> bool:
    value = text or ""
    if not value.strip():
        return False
    numbered = len(
        re.findall(
            r"(?im)^\s*(?:item\s*)?#?\s*(?:\d{1,2}(?:\.\d+)?|[A-Z]|[IVXLC]+)[\.\):]\s+.{6,}$",
            value,
        )
    )
    subjects = len(re.findall(r"(?im)^\s*subject\s*:\s+.{6,}$", value))
    pages = len(re.findall(r"\[PAGE\s+\d+\]", value, flags=re.IGNORECASE))
    paragraphs = len(llm_mod.iter_fallback_paragraphs(value))
    return numbered >= 4 or subjects >= 4 or (numbered >= 2 and pages >= 3) or paragraphs >= 8


class HeuristicOnlyLocalAI:
    def extract_agenda(self, text: str) -> list[dict[str, Any]]:
        local_ai = llm_mod.LocalAI()
        original_get_provider = local_ai._get_provider
        try:
            # Maintenance mode reuses the deterministic parser directly so backlog
            # chunks do not burn time timing out before landing in the same fallback.
            local_ai._get_provider = lambda: None
            return llm_mod.LocalAI.extract_agenda(local_ai, text)
        finally:
            local_ai._get_provider = original_get_provider


def persist_segmented_agenda(
    session,
    *,
    catalog: Catalog,
    doc: Document,
    items_data: list[dict[str, Any]],
) -> str:
    if items_data:
        persist_agenda_items(session, catalog.id, doc.event_id, items_data)
        catalog.agenda_segmentation_status = "complete"
        catalog.agenda_segmentation_item_count = len(items_data)
        catalog.agenda_segmentation_attempted_at = datetime.now(timezone.utc)
        catalog.agenda_segmentation_error = None
        session.commit()
        return "complete"
    catalog.agenda_segmentation_status = "empty"
    catalog.agenda_segmentation_item_count = 0
    catalog.agenda_segmentation_attempted_at = datetime.now(timezone.utc)
    catalog.agenda_segmentation_error = None
    session.commit()
    return "empty"


def _empty_segment_result(status: str = "other", **extra: Any) -> dict[str, Any]:
    result = {
        "status": status,
        "llm_attempted": 0,
        "llm_skipped_heuristic_first": 0,
        "heuristic_complete": 0,
        "source_used": None,
    }
    result.update(extra)
    return result


def segment_catalog_with_mode(catalog_id: int, *, segment_mode: str = "normal") -> dict[str, Any]:
    with db_session() as session:
        try:
            catalog = session.get(Catalog, catalog_id)
            if not catalog or not catalog.content:
                return _empty_segment_result()
            doc = session.query(Document).filter_by(catalog_id=catalog.id).first()
            if not doc or not doc.event_id:
                return _empty_segment_result()
            classification = classify_catalog_bad_content(
                catalog,
                document_category=getattr(doc, "category", None),
                include_document_shape=True,
                has_viable_structured_source=has_viable_structured_agenda_source(session, catalog, doc),
            )
            if classification:
                catalog.agenda_segmentation_status = "failed"
                catalog.agenda_segmentation_item_count = 0
                catalog.agenda_segmentation_attempted_at = datetime.now(timezone.utc)
                catalog.agenda_segmentation_error = classification.reason
                session.commit()
                return _empty_segment_result("failed", error=classification.reason)

            if segment_mode == "maintenance" and looks_structured_enough_for_heuristic_segmentation(catalog.content):
                heuristic_resolved = resolve_agenda_items(session, catalog, doc, HeuristicOnlyLocalAI())
                status = persist_segmented_agenda(session, catalog=catalog, doc=doc, items_data=heuristic_resolved["items"])
                return _empty_segment_result(
                    status,
                    llm_skipped_heuristic_first=1,
                    heuristic_complete=int(status == "complete"),
                    source_used="heuristic",
                )

            resolved = resolve_agenda_items(session, catalog, doc, llm_mod.LocalAI())
            status = persist_segmented_agenda(session, catalog=catalog, doc=doc, items_data=resolved["items"])
            return _empty_segment_result(
                status,
                llm_attempted=int(bool(resolved.get("llm_fallback_invoked"))),
                source_used=resolved.get("source_used"),
            )
        except SQLAlchemyError as exc:
            try:
                catalog = session.get(Catalog, catalog_id)
                if catalog:
                    catalog.agenda_segmentation_status = "failed"
                    catalog.agenda_segmentation_item_count = 0
                    catalog.agenda_segmentation_attempted_at = datetime.now(timezone.utc)
                    catalog.agenda_segmentation_error = str(exc)[:500]
                    session.commit()
            except Exception as catalog_error:
                # If the failure row cannot be persisted, the returned failed status still
                # tells the caller the segment step did not complete for this catalog.
                logger.warning(
                    "agenda_segmentation.failure_persist_failed catalog_id=%s error=%s",
                    catalog_id,
                    catalog_error,
                )
            return _empty_segment_result("failed", error=str(exc))


def build_agenda_summary_input_bundle(
    *,
    catalog,
    document,
    agenda_items,
    include_meeting_context: bool = False,
    max_input_chars: int | None = None,
    min_reserved_output_chars: int | None = None,
) -> dict[str, Any]:
    resolved_max_input_chars = (
        AGENDA_SUMMARY_MAX_INPUT_CHARS if max_input_chars is None else max_input_chars
    )
    resolved_min_reserved_output_chars = (
        AGENDA_SUMMARY_MIN_RESERVED_OUTPUT_CHARS
        if min_reserved_output_chars is None
        else min_reserved_output_chars
    )
    return agenda_summary_maintenance_mod.build_agenda_summary_input_bundle(
        catalog=catalog,
        document=document,
        agenda_items=agenda_items,
        include_meeting_context=include_meeting_context,
        max_input_chars=resolved_max_input_chars,
        min_reserved_output_chars=resolved_min_reserved_output_chars,
    )


def persist_agenda_summary(
    *,
    catalog,
    summary: str,
    content_hash: str | None,
    agenda_items_hash: str | None,
) -> dict[str, Any]:
    return agenda_summary_maintenance_mod.persist_agenda_summary(
        catalog=catalog,
        summary=summary,
        content_hash=content_hash,
        agenda_items_hash=agenda_items_hash,
    )


def build_deterministic_agenda_summary_payloads(
    catalog_ids: list[int],
    *,
    reindex_callback: Callable[[list[int]], Any] | None = None,
    embed_callback: Callable[[list[int]], Any] | None = None,
) -> dict[str, Any]:
    return agenda_summary_maintenance_mod.build_deterministic_agenda_summary_payloads(
        catalog_ids,
        reindex_callback=reindex_callback,
        embed_callback=embed_callback,
        max_input_chars=AGENDA_SUMMARY_MAX_INPUT_CHARS,
        min_reserved_output_chars=AGENDA_SUMMARY_MIN_RESERVED_OUTPUT_CHARS,
        session_factory=db_session,
    )


def build_deterministic_agenda_summary_payload(
    catalog_id: int,
    *,
    reindex_callback: Callable[[int], Any] | None = None,
    embed_callback: Callable[[int], Any] | None = None,
) -> dict[str, Any]:
    return agenda_summary_maintenance_mod.build_deterministic_agenda_summary_payload(
        catalog_id,
        reindex_callback=reindex_callback,
        embed_callback=embed_callback,
        build_payloads_callable=build_deterministic_agenda_summary_payloads,
    )


def summarize_catalog_with_optional_fallback(
    catalog_id: int,
    *,
    summary_fallback_mode: str = "none",
    generate_summary_callable: Callable[[int], dict[str, Any] | None],
    deterministic_summary_callable: Callable[[int], dict[str, Any]],
) -> dict[str, Any]:
    return agenda_summary_maintenance_mod.summarize_catalog_with_optional_fallback(
        catalog_id,
        summary_fallback_mode=summary_fallback_mode,
        generate_summary_callable=generate_summary_callable,
        deterministic_summary_callable=deterministic_summary_callable,
        capture_summary_fallback_events_factory=capture_summary_fallback_events,
    )


def summarize_catalog_with_maintenance_mode(
    catalog_id: int,
    *,
    summary_fallback_mode: str = "none",
    generate_summary_callable: Callable[[int], dict[str, Any] | None],
    deterministic_summary_callable: Callable[[int], dict[str, Any]],
) -> dict[str, Any]:
    """
    Maintenance hydration is allowed to skip agenda LLM summaries entirely.

    Why:
    Agenda backlog runs already have structured agenda items, and baseline profiling
    showed we were often paying for an LLM agenda summary only to replace it with the
    same deterministic agenda-items summary. Interactive one-off summary generation
    still uses the normal task path; this optimization is only for maintenance flows.
    """
    with db_session() as session:
        doc = session.query(Document).filter_by(catalog_id=catalog_id).first()
        doc_kind = agenda_summary_maintenance_mod.normalize_summary_doc_kind(
            doc.category if doc else "unknown"
        )

    if doc_kind == "agenda":
        return agenda_summary_maintenance_mod.summarize_catalog_with_maintenance_mode(
            catalog_id,
            summary_fallback_mode=summary_fallback_mode,
            generate_summary_callable=generate_summary_callable,
            deterministic_summary_callable=deterministic_summary_callable,
            session_factory=db_session,
            capture_summary_fallback_events_factory=capture_summary_fallback_events,
        )

    return summarize_catalog_with_optional_fallback(
        catalog_id,
        summary_fallback_mode=summary_fallback_mode,
        generate_summary_callable=generate_summary_callable,
        deterministic_summary_callable=deterministic_summary_callable,
    )

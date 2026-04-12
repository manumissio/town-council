from __future__ import annotations

import logging
import re
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.exc import SQLAlchemyError

from pipeline import llm as llm_mod
from pipeline import llm_provider as llm_provider_mod
from pipeline.agenda_resolver import has_viable_structured_agenda_source, resolve_agenda_items
from pipeline.agenda_service import persist_agenda_items
from pipeline.db_session import db_session
from pipeline.laserfiche_error_pages import classify_catalog_bad_content
from pipeline.models import Catalog, Document

logger = logging.getLogger(__name__)


@contextmanager
def provider_timeout_override(
    *,
    segment_timeout_seconds: int | None = None,
    summary_timeout_seconds: int | None = None,
):
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
    local_ai_logger = logging.getLogger("local-ai")
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
    local_ai_logger.addHandler(handler)
    try:
        yield counts
    finally:
        local_ai_logger.removeHandler(handler)


@contextmanager
def capture_summary_fallback_events() -> dict[str, int]:
    local_ai_logger = logging.getLogger("local-ai")
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
    local_ai_logger.addHandler(handler)
    try:
        yield counts
    finally:
        local_ai_logger.removeHandler(handler)


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
    segment_result = {
        "status": status,
        "llm_attempted": 0,
        "llm_skipped_heuristic_first": 0,
        "heuristic_complete": 0,
        "source_used": None,
    }
    segment_result.update(extra)
    return segment_result


def segment_catalog_with_mode(
    catalog_id: int,
    *,
    segment_mode: str = "normal",
    session_factory=db_session,
    has_viable_structured_source=has_viable_structured_agenda_source,
) -> dict[str, Any]:
    with session_factory() as session:
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
                has_viable_structured_source=has_viable_structured_source(session, catalog, doc),
            )
            if classification:
                catalog.agenda_segmentation_status = "failed"
                catalog.agenda_segmentation_item_count = 0
                catalog.agenda_segmentation_attempted_at = datetime.now(timezone.utc)
                catalog.agenda_segmentation_error = classification.reason
                session.commit()
                return _empty_segment_result("failed", error=classification.reason)

            if segment_mode == "maintenance" and looks_structured_enough_for_heuristic_segmentation(
                catalog.content
            ):
                heuristic_resolved = resolve_agenda_items(session, catalog, doc, HeuristicOnlyLocalAI())
                status = persist_segmented_agenda(
                    session,
                    catalog=catalog,
                    doc=doc,
                    items_data=heuristic_resolved["items"],
                )
                return _empty_segment_result(
                    status,
                    llm_skipped_heuristic_first=1,
                    heuristic_complete=int(status == "complete"),
                    source_used="heuristic",
                )

            resolved = resolve_agenda_items(session, catalog, doc, llm_mod.LocalAI())
            status = persist_segmented_agenda(
                session,
                catalog=catalog,
                doc=doc,
                items_data=resolved["items"],
            )
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
            except SQLAlchemyError as catalog_error:
                # If the failure row cannot be persisted, the returned failed status still
                # tells the caller the segment step did not complete for this catalog.
                logger.warning(
                    "agenda_segmentation.failure_persist_failed catalog_id=%s error=%s",
                    catalog_id,
                    catalog_error,
                )
            return _empty_segment_result("failed", error=str(exc))

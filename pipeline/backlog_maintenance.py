from __future__ import annotations

import logging
import re
from collections import Counter, defaultdict
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Callable

from sqlalchemy.exc import SQLAlchemyError

from pipeline import llm as llm_mod
from pipeline import llm_provider as llm_provider_mod
from pipeline.agenda_resolver import has_viable_structured_agenda_source, resolve_agenda_items
from pipeline.agenda_service import persist_agenda_items
from pipeline.config import AGENDA_SUMMARY_MAX_INPUT_CHARS, AGENDA_SUMMARY_MIN_RESERVED_OUTPUT_CHARS
from pipeline.content_hash import compute_content_hash
from pipeline.db_session import db_session
from pipeline.document_kinds import normalize_summary_doc_kind
from pipeline.laserfiche_error_pages import classify_catalog_bad_content
from pipeline.models import AgendaItem, Catalog, Document


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
            except Exception:
                pass
            return _empty_segment_result("failed", error=str(exc))


def build_deterministic_agenda_summary_payload(
    catalog_id: int,
    *,
    reindex_callback: Callable[[int], Any] | None = None,
    embed_callback: Callable[[int], Any] | None = None,
) -> dict[str, Any]:
    batch = build_deterministic_agenda_summary_payloads(
        [catalog_id],
        reindex_callback=(lambda catalog_ids: reindex_callback(catalog_id)) if reindex_callback is not None else None,
        embed_callback=(lambda catalog_ids: embed_callback(catalog_id)) if embed_callback is not None else None,
    )
    return batch["results"].get(catalog_id, {"status": "error", "error": "Catalog not found"})


def _build_deterministic_agenda_summary_result(existing_items: list[AgendaItem]) -> dict[str, Any]:
    if not existing_items:
        return {
            "status": "not_generated_yet",
            "reason": "Agenda summary requires segmented agenda items. Run segmentation first.",
            "summary": None,
        }

    summary_items: list[dict[str, Any]] = []
    candidate_items_total = 0
    input_chars = 0
    max_input_chars = max(1000, AGENDA_SUMMARY_MAX_INPUT_CHARS - AGENDA_SUMMARY_MIN_RESERVED_OUTPUT_CHARS)
    for item in existing_items:
        title = (item.title or "").strip()
        if not title:
            continue
        if llm_mod._looks_like_agenda_segmentation_boilerplate(title):
            continue
        description = (item.description or "").strip()
        serialized = title if not description else f"{title} - {description}"
        if llm_mod._should_drop_from_agenda_summary(serialized):
            continue
        candidate_items_total += 1
        payload = {
            "title": title,
            "description": description,
            "classification": (item.classification or "").strip(),
            "result": (item.result or "").strip(),
            "page_number": int(item.page_number or 0),
        }
        item_block = (
            f"Title: {payload['title']}\n"
            f"Description: {payload['description']}\n"
            f"Classification: {payload['classification']}\n"
            f"Result: {payload['result']}\n"
            f"Page: {payload['page_number']}\n\n"
        )
        if (input_chars + len(item_block)) > max_input_chars:
            break
        summary_items.append(payload)
        input_chars += len(item_block)

    if not summary_items:
        return {
            "status": "blocked_low_signal",
            "reason": "No substantive agenda items detected after boilerplate filtering. Re-segment the agenda.",
            "summary": None,
        }

    summary = llm_mod._deterministic_agenda_items_summary(
        summary_items,
        truncation_meta={
            "items_total": candidate_items_total,
            "items_included": len(summary_items),
            "items_truncated": max(0, candidate_items_total - len(summary_items)),
            "input_chars": input_chars,
        },
    )
    return {"status": "complete", "summary": summary}


def build_deterministic_agenda_summary_payloads(
    catalog_ids: list[int],
    *,
    reindex_callback: Callable[[list[int]], Any] | None = None,
    embed_callback: Callable[[list[int]], Any] | None = None,
) -> dict[str, Any]:
    ordered_catalog_ids = [int(catalog_id) for catalog_id in catalog_ids]
    if not ordered_catalog_ids:
        return {
            "results": {},
            "changed_catalog_ids": [],
            "reindex_summary": {"catalogs_considered": 0, "catalogs_reindexed": 0, "catalogs_failed": 0, "failed_catalog_ids": []},
            "embed_summary": {"catalogs_considered": 0, "embed_enqueued": 0, "embed_dispatch_failed": 0, "failed_catalog_ids": []},
        }

    with db_session() as session:
        catalogs = {
            catalog.id: catalog
            for catalog in session.query(Catalog).filter(Catalog.id.in_(ordered_catalog_ids)).all()
        }
        documents_by_catalog_id: dict[int, Document] = {}
        for document in (
            session.query(Document)
            .filter(Document.catalog_id.in_(ordered_catalog_ids))
            .order_by(Document.catalog_id, Document.id)
            .all()
        ):
            documents_by_catalog_id.setdefault(document.catalog_id, document)

        agenda_items_by_catalog_id: dict[int, list[AgendaItem]] = defaultdict(list)
        for item in (
            session.query(AgendaItem)
            .filter(AgendaItem.catalog_id.in_(ordered_catalog_ids))
            .order_by(AgendaItem.catalog_id, AgendaItem.order)
            .all()
        ):
            agenda_items_by_catalog_id[item.catalog_id].append(item)

        results: dict[int, dict[str, Any]] = {}
        changed_catalog_ids: list[int] = []
        for catalog_id in ordered_catalog_ids:
            catalog = catalogs.get(catalog_id)
            if not catalog:
                results[catalog_id] = {"status": "error", "error": "Catalog not found"}
                continue
            classification = classify_catalog_bad_content(catalog)
            if classification:
                results[catalog_id] = {"status": "error", "error": classification.reason}
                continue
            if catalog_id not in documents_by_catalog_id:
                results[catalog_id] = {"status": "error", "error": "Document not found"}
                continue

            content_hash = compute_content_hash(catalog.content) if (catalog.content or "") else None
            result = _build_deterministic_agenda_summary_result(agenda_items_by_catalog_id.get(catalog_id, []))
            if result.get("status") != "complete":
                results[catalog_id] = result
                continue

            summary = str(result.get("summary") or "")
            prior_summary = catalog.summary
            prior_summary_source_hash = catalog.summary_source_hash
            catalog.summary = summary
            if content_hash:
                catalog.content_hash = content_hash
                catalog.summary_source_hash = content_hash

            changed = bool(prior_summary != summary or prior_summary_source_hash != content_hash)
            if changed:
                changed_catalog_ids.append(catalog_id)
            results[catalog_id] = {
                **result,
                "changed": changed,
                "completion_mode": "agenda_deterministic",
            }
        session.commit()

    reindex_summary = {"catalogs_considered": 0, "catalogs_reindexed": 0, "catalogs_failed": 0, "failed_catalog_ids": []}
    if changed_catalog_ids and reindex_callback is not None:
        try:
            payload = reindex_callback(changed_catalog_ids)
            if isinstance(payload, dict):
                reindex_summary = {
                    "catalogs_considered": int(payload.get("catalogs_considered") or len(changed_catalog_ids)),
                    "catalogs_reindexed": int(payload.get("catalogs_reindexed") or 0),
                    "catalogs_failed": int(payload.get("catalogs_failed") or 0),
                    "failed_catalog_ids": list(payload.get("failed_catalog_ids") or []),
                }
        except Exception as exc:
            reindex_summary = {
                "catalogs_considered": len(changed_catalog_ids),
                "catalogs_reindexed": 0,
                "catalogs_failed": len(changed_catalog_ids),
                "failed_catalog_ids": list(changed_catalog_ids),
                "error": str(exc),
            }

    embed_summary = {"catalogs_considered": 0, "embed_enqueued": 0, "embed_dispatch_failed": 0, "failed_catalog_ids": []}
    if changed_catalog_ids and embed_callback is not None:
        try:
            payload = embed_callback(changed_catalog_ids)
            if isinstance(payload, dict):
                embed_summary = {
                    "catalogs_considered": int(payload.get("catalogs_considered") or len(changed_catalog_ids)),
                    "embed_enqueued": int(payload.get("embed_enqueued") or 0),
                    "embed_dispatch_failed": int(payload.get("embed_dispatch_failed") or 0),
                    "failed_catalog_ids": list(payload.get("failed_catalog_ids") or []),
                }
        except Exception as exc:
            embed_summary = {
                "catalogs_considered": len(changed_catalog_ids),
                "embed_enqueued": 0,
                "embed_dispatch_failed": len(changed_catalog_ids),
                "failed_catalog_ids": list(changed_catalog_ids),
                "error": str(exc),
            }

    return {
        "results": results,
        "changed_catalog_ids": changed_catalog_ids,
        "reindex_summary": reindex_summary,
        "embed_summary": embed_summary,
    }


def _provider_failure_detected(result: dict[str, Any], fallback_events: dict[str, int]) -> bool:
    if fallback_events.get("timeout", 0) or fallback_events.get("unavailable", 0):
        return True
    lowered_error = str(result.get("error") or "").lower()
    return any(token in lowered_error for token in ("timed out", "timeout", "unavailable", "connection"))


def summarize_catalog_with_optional_fallback(
    catalog_id: int,
    *,
    summary_fallback_mode: str = "none",
    generate_summary_callable: Callable[[int], dict[str, Any] | None],
    deterministic_summary_callable: Callable[[int], dict[str, Any]],
) -> dict[str, Any]:
    with capture_summary_fallback_events() as fallback_events:
        try:
            result = generate_summary_callable(catalog_id) or {}
        except Exception as exc:
            result = {"status": "error", "error": str(exc)}
    status = str(result.get("status") or "other")
    if (
        summary_fallback_mode == "deterministic"
        and status == "error"
        and _provider_failure_detected(result, fallback_events)
    ):
        fallback_result = deterministic_summary_callable(catalog_id)
        fallback_result["provider_failure"] = dict(fallback_events)
        return fallback_result
    if status == "complete":
        result["completion_mode"] = "llm"
    return result


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
        doc_kind = normalize_summary_doc_kind(doc.category if doc else "unknown")

    if doc_kind == "agenda":
        try:
            result = deterministic_summary_callable(catalog_id)
        except Exception as exc:
            return {"status": "error", "error": str(exc)}
        if str(result.get("status") or "other") == "complete":
            result["completion_mode"] = "agenda_deterministic"
        return result

    return summarize_catalog_with_optional_fallback(
        catalog_id,
        summary_fallback_mode=summary_fallback_mode,
        generate_summary_callable=generate_summary_callable,
        deterministic_summary_callable=deterministic_summary_callable,
    )

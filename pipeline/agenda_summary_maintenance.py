from __future__ import annotations

from collections import defaultdict
from contextlib import nullcontext
from time import perf_counter
from typing import Any, Callable

from celery.exceptions import CeleryError
from kombu.exceptions import KombuError
from meilisearch.errors import MeilisearchError
from sqlalchemy.exc import SQLAlchemyError

from pipeline import llm as llm_mod
from pipeline.config import AGENDA_SUMMARY_MAX_INPUT_CHARS, AGENDA_SUMMARY_MIN_RESERVED_OUTPUT_CHARS
from pipeline.content_hash import compute_content_hash
from pipeline.db_session import db_session
from pipeline.document_kinds import normalize_summary_doc_kind
from pipeline.laserfiche_error_pages import classify_catalog_bad_content
from pipeline.models import AgendaItem, Catalog, Document
from pipeline.summary_freshness import compute_agenda_items_hash, compute_summary_source_hash

AGENDA_SUMMARY_READY_STATUS = "ready"
AGENDA_SUMMARY_SEGMENTATION_REQUIRED_REASON = (
    "Agenda summary requires segmented agenda items. Run segmentation first."
)
AGENDA_SUMMARY_BLOCKED_LOW_SIGNAL_REASON = (
    "No substantive agenda items detected after boilerplate filtering. Re-segment the agenda."
)
AGENDA_SUMMARY_CATALOG_NOT_FOUND_ERROR = "Catalog not found"
AGENDA_SUMMARY_DOCUMENT_NOT_FOUND_ERROR = "Document not found"
AGENDA_SUMMARY_BUNDLE_BUILD_MS = "agenda_summary_bundle_build_ms"
AGENDA_SUMMARY_RENDER_MS = "agenda_summary_render_ms"
AGENDA_SUMMARY_PERSIST_MS = "agenda_summary_persist_ms"
AGENDA_SUMMARY_REINDEX_MS = "agenda_summary_reindex_ms"
AGENDA_SUMMARY_EMBED_DISPATCH_MS = "agenda_summary_embed_dispatch_ms"
AGENDA_SUMMARY_TIMING_KEYS = (
    AGENDA_SUMMARY_BUNDLE_BUILD_MS,
    AGENDA_SUMMARY_RENDER_MS,
    AGENDA_SUMMARY_PERSIST_MS,
    AGENDA_SUMMARY_REINDEX_MS,
    AGENDA_SUMMARY_EMBED_DISPATCH_MS,
)

_PROVIDER_FAILURE_TOKENS = ("timed out", "timeout", "unavailable", "connection")
AGENDA_SUMMARY_REINDEX_ERRORS = (
    MeilisearchError,
    SQLAlchemyError,
    RuntimeError,
    TypeError,
    ValueError,
    KeyError,
)
AGENDA_SUMMARY_EMBED_DISPATCH_ERRORS = (
    CeleryError,
    KombuError,
    RuntimeError,
    TypeError,
    ValueError,
    KeyError,
)
AGENDA_SUMMARY_CALLABLE_ERRORS = (RuntimeError, TypeError, ValueError, KeyError)


def build_deterministic_agenda_summary_payload(
    catalog_id: int,
    *,
    reindex_callback: Callable[[int], Any] | None = None,
    embed_callback: Callable[[int], Any] | None = None,
    build_payloads_callable: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    batch_builder = build_payloads_callable or build_deterministic_agenda_summary_payloads
    batch = batch_builder(
        [catalog_id],
        reindex_callback=(
            (lambda catalog_ids: reindex_callback(catalog_id)) if reindex_callback is not None else None
        ),
        embed_callback=(
            (lambda catalog_ids: embed_callback(catalog_id)) if embed_callback is not None else None
        ),
    )
    return batch["results"].get(
        catalog_id,
        {"status": "error", "error": AGENDA_SUMMARY_CATALOG_NOT_FOUND_ERROR},
    )


def _agenda_summary_ready_payload(
    *,
    catalog: Catalog,
    content_hash: str | None,
    agenda_items_hash: str | None,
    summary_items: list[dict[str, Any]],
    truncation_meta: dict[str, int],
    meeting_title: str,
    meeting_date: str,
) -> dict[str, Any]:
    return {
        "status": AGENDA_SUMMARY_READY_STATUS,
        "catalog": catalog,
        "content_hash": content_hash,
        "agenda_items_hash": agenda_items_hash,
        "summary_items": summary_items,
        "truncation_meta": truncation_meta,
        "meeting_title": meeting_title,
        "meeting_date": meeting_date,
    }


def _agenda_summary_item_payload(item: AgendaItem) -> dict[str, Any] | None:
    title = (item.title or "").strip()
    if not title:
        return None
    if llm_mod._looks_like_agenda_segmentation_boilerplate(title):
        return None

    description = (item.description or "").strip()
    serialized = title if not description else f"{title} - {description}"
    if llm_mod._should_drop_from_agenda_summary(serialized):
        return None

    return {
        "title": title,
        "description": description,
        "classification": (item.classification or "").strip(),
        "result": (item.result or "").strip(),
        "page_number": int(item.page_number or 0),
    }


def _agenda_summary_item_block(summary_item: dict[str, Any]) -> str:
    return (
        f"Title: {summary_item['title']}\n"
        f"Description: {summary_item['description']}\n"
        f"Classification: {summary_item['classification']}\n"
        f"Result: {summary_item['result']}\n"
        f"Page: {summary_item['page_number']}\n\n"
    )


def _empty_agenda_summary_timings() -> dict[str, float]:
    return {metric_name: 0 for metric_name in AGENDA_SUMMARY_TIMING_KEYS}


def _elapsed_millis(started_at: float) -> float:
    return (perf_counter() - started_at) * 1000.0


def _rounded_agenda_summary_timings(agenda_summary_timings: dict[str, float]) -> dict[str, int]:
    return {
        metric_name: int(round(agenda_summary_timings.get(metric_name, 0.0)))
        for metric_name in AGENDA_SUMMARY_TIMING_KEYS
    }


def build_agenda_summary_input_bundle(
    *,
    catalog: Catalog | None,
    document: Document | None,
    agenda_items: list[AgendaItem],
    include_meeting_context: bool = False,
    max_input_chars: int = AGENDA_SUMMARY_MAX_INPUT_CHARS,
    min_reserved_output_chars: int = AGENDA_SUMMARY_MIN_RESERVED_OUTPUT_CHARS,
) -> dict[str, Any]:
    if catalog is None:
        return {"status": "error", "error": AGENDA_SUMMARY_CATALOG_NOT_FOUND_ERROR}
    if document is None:
        return {"status": "error", "error": AGENDA_SUMMARY_DOCUMENT_NOT_FOUND_ERROR}
    if not agenda_items:
        return {
            "status": "not_generated_yet",
            "reason": AGENDA_SUMMARY_SEGMENTATION_REQUIRED_REASON,
            "summary": None,
        }

    summary_items: list[dict[str, Any]] = []
    candidate_items_total = 0
    input_chars = 0
    summary_payload_budget = max(1000, int(max_input_chars) - int(min_reserved_output_chars))
    for item in agenda_items:
        summary_item = _agenda_summary_item_payload(item)
        if summary_item is None:
            continue
        candidate_items_total += 1
        item_block = _agenda_summary_item_block(summary_item)
        if (input_chars + len(item_block)) > summary_payload_budget:
            break
        summary_items.append(summary_item)
        input_chars += len(item_block)

    if not summary_items:
        return {
            "status": "blocked_low_signal",
            "reason": AGENDA_SUMMARY_BLOCKED_LOW_SIGNAL_REASON,
            "summary": None,
        }

    content_hash = compute_content_hash(catalog.content) if (catalog.content or "") else None
    agenda_items_hash = compute_agenda_items_hash(agenda_items)
    truncation_meta = {
        "items_total": candidate_items_total,
        "items_included": len(summary_items),
        "items_truncated": max(0, candidate_items_total - len(summary_items)),
        "input_chars": input_chars,
    }
    meeting_title = ""
    meeting_date = ""
    if include_meeting_context:
        event = getattr(document, "event", None)
        meeting_title = event.name if event and event.name else ""
        meeting_date = str(event.record_date) if event and event.record_date else ""
    return _agenda_summary_ready_payload(
        catalog=catalog,
        content_hash=content_hash,
        agenda_items_hash=agenda_items_hash,
        summary_items=summary_items,
        truncation_meta=truncation_meta,
        meeting_title=meeting_title,
        meeting_date=meeting_date,
    )


def _build_deterministic_agenda_summary_result(summary_bundle: dict[str, Any]) -> dict[str, Any]:
    summary = llm_mod._deterministic_agenda_items_summary(
        summary_bundle["summary_items"],
        truncation_meta=summary_bundle["truncation_meta"],
    )
    return {"status": "complete", "summary": summary}


def _time_agenda_summary_bundle_build(
    agenda_summary_timings: dict[str, float],
    *,
    catalog: Catalog | None,
    document: Document | None,
    agenda_items: list[AgendaItem],
    max_input_chars: int,
    min_reserved_output_chars: int,
) -> dict[str, Any]:
    started_at = perf_counter()
    summary_bundle = build_agenda_summary_input_bundle(
        catalog=catalog,
        document=document,
        agenda_items=agenda_items,
        max_input_chars=max_input_chars,
        min_reserved_output_chars=min_reserved_output_chars,
    )
    agenda_summary_timings[AGENDA_SUMMARY_BUNDLE_BUILD_MS] += _elapsed_millis(started_at)
    return summary_bundle


def _time_agenda_summary_render(
    agenda_summary_timings: dict[str, float],
    summary_bundle: dict[str, Any],
) -> dict[str, Any]:
    started_at = perf_counter()
    summary_result = _build_deterministic_agenda_summary_result(summary_bundle)
    agenda_summary_timings[AGENDA_SUMMARY_RENDER_MS] += _elapsed_millis(started_at)
    return summary_result


def _empty_callback_summary(
    *,
    catalogs_considered_key: str,
    success_key: str,
    failure_key: str,
) -> dict[str, Any]:
    return {
        catalogs_considered_key: 0,
        success_key: 0,
        failure_key: 0,
        "failed_catalog_ids": [],
    }


def _time_reindex_callback(
    agenda_summary_timings: dict[str, float],
    changed_catalog_ids: list[int],
    reindex_callback: Callable[[list[int]], Any] | None,
) -> dict[str, Any]:
    reindex_summary = _empty_callback_summary(
        catalogs_considered_key="catalogs_considered",
        success_key="catalogs_reindexed",
        failure_key="catalogs_failed",
    )
    if not changed_catalog_ids or reindex_callback is None:
        return reindex_summary

    started_at = perf_counter()
    try:
        payload = reindex_callback(changed_catalog_ids)
        if isinstance(payload, dict):
            reindex_summary = {
                "catalogs_considered": int(payload.get("catalogs_considered") or len(changed_catalog_ids)),
                "catalogs_reindexed": int(payload.get("catalogs_reindexed") or 0),
                "catalogs_failed": int(payload.get("catalogs_failed") or 0),
                "failed_catalog_ids": list(payload.get("failed_catalog_ids") or []),
            }
    except AGENDA_SUMMARY_REINDEX_ERRORS as error:
        # Reindex is post-commit maintenance work. If it fails, the summary write is
        # still durable and the caller needs failure details instead of a rollback.
        reindex_summary = {
            "catalogs_considered": len(changed_catalog_ids),
            "catalogs_reindexed": 0,
            "catalogs_failed": len(changed_catalog_ids),
            "failed_catalog_ids": list(changed_catalog_ids),
            "error": str(error),
        }
    finally:
        agenda_summary_timings[AGENDA_SUMMARY_REINDEX_MS] += _elapsed_millis(started_at)
    return reindex_summary


def _time_embed_callback(
    agenda_summary_timings: dict[str, float],
    changed_catalog_ids: list[int],
    embed_callback: Callable[[list[int]], Any] | None,
) -> dict[str, Any]:
    embed_summary = _empty_callback_summary(
        catalogs_considered_key="catalogs_considered",
        success_key="embed_enqueued",
        failure_key="embed_dispatch_failed",
    )
    if not changed_catalog_ids or embed_callback is None:
        return embed_summary

    started_at = perf_counter()
    try:
        payload = embed_callback(changed_catalog_ids)
        if isinstance(payload, dict):
            embed_summary = {
                "catalogs_considered": int(payload.get("catalogs_considered") or len(changed_catalog_ids)),
                "embed_enqueued": int(payload.get("embed_enqueued") or 0),
                "embed_dispatch_failed": int(payload.get("embed_dispatch_failed") or 0),
                "failed_catalog_ids": list(payload.get("failed_catalog_ids") or []),
            }
    except AGENDA_SUMMARY_EMBED_DISPATCH_ERRORS as error:
        # Embed dispatch is also post-commit. We surface the failure so maintenance
        # reporting stays accurate without downgrading the durable summary write.
        embed_summary = {
            "catalogs_considered": len(changed_catalog_ids),
            "embed_enqueued": 0,
            "embed_dispatch_failed": len(changed_catalog_ids),
            "failed_catalog_ids": list(changed_catalog_ids),
            "error": str(error),
        }
    finally:
        agenda_summary_timings[AGENDA_SUMMARY_EMBED_DISPATCH_MS] += _elapsed_millis(started_at)
    return embed_summary


def persist_agenda_summary(
    *,
    catalog: Catalog,
    summary: str,
    content_hash: str | None,
    agenda_items_hash: str | None,
) -> dict[str, Any]:
    prior_summary = catalog.summary
    prior_summary_source_hash = catalog.summary_source_hash
    prior_agenda_items_hash = catalog.agenda_items_hash
    summary_source_hash = compute_summary_source_hash(
        "agenda",
        content_hash=content_hash,
        agenda_items_hash=agenda_items_hash,
    )
    catalog.summary = summary
    if content_hash:
        catalog.content_hash = content_hash
    catalog.agenda_items_hash = agenda_items_hash
    if summary_source_hash:
        catalog.summary_source_hash = summary_source_hash

    changed = bool(
        prior_summary != summary
        or prior_summary_source_hash != summary_source_hash
        or prior_agenda_items_hash != agenda_items_hash
    )
    return {"status": "complete", "summary": summary, "changed": changed}


def build_deterministic_agenda_summary_payloads(
    catalog_ids: list[int],
    *,
    reindex_callback: Callable[[list[int]], Any] | None = None,
    embed_callback: Callable[[list[int]], Any] | None = None,
    max_input_chars: int = AGENDA_SUMMARY_MAX_INPUT_CHARS,
    min_reserved_output_chars: int = AGENDA_SUMMARY_MIN_RESERVED_OUTPUT_CHARS,
    session_factory: Callable[[], Any] = db_session,
) -> dict[str, Any]:
    ordered_catalog_ids = [int(catalog_id) for catalog_id in catalog_ids]
    if not ordered_catalog_ids:
        return {
            "results": {},
            "changed_catalog_ids": [],
            "reindex_summary": _empty_callback_summary(
                catalogs_considered_key="catalogs_considered",
                success_key="catalogs_reindexed",
                failure_key="catalogs_failed",
            ),
            "embed_summary": _empty_callback_summary(
                catalogs_considered_key="catalogs_considered",
                success_key="embed_enqueued",
                failure_key="embed_dispatch_failed",
            ),
            "agenda_summary_timings": _rounded_agenda_summary_timings(_empty_agenda_summary_timings()),
        }

    agenda_summary_timings = _empty_agenda_summary_timings()
    with session_factory() as session:
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
                results[catalog_id] = {"status": "error", "error": AGENDA_SUMMARY_CATALOG_NOT_FOUND_ERROR}
                continue
            classification = classify_catalog_bad_content(catalog)
            if classification:
                results[catalog_id] = {"status": "error", "error": classification.reason}
                continue

            summary_bundle = _time_agenda_summary_bundle_build(
                agenda_summary_timings,
                catalog=catalog,
                document=documents_by_catalog_id.get(catalog_id),
                agenda_items=agenda_items_by_catalog_id.get(catalog_id, []),
                max_input_chars=max_input_chars,
                min_reserved_output_chars=min_reserved_output_chars,
            )
            if summary_bundle.get("status") != AGENDA_SUMMARY_READY_STATUS:
                results[catalog_id] = summary_bundle
                continue

            summary_result = _time_agenda_summary_render(agenda_summary_timings, summary_bundle)
            persist_started_at = perf_counter()
            persisted_result = persist_agenda_summary(
                catalog=catalog,
                summary=str(summary_result.get("summary") or ""),
                content_hash=summary_bundle["content_hash"],
                agenda_items_hash=summary_bundle["agenda_items_hash"],
            )
            agenda_summary_timings[AGENDA_SUMMARY_PERSIST_MS] += _elapsed_millis(persist_started_at)
            if persisted_result["changed"]:
                changed_catalog_ids.append(catalog_id)
            results[catalog_id] = {**persisted_result, "completion_mode": "agenda_deterministic"}

        commit_started_at = perf_counter()
        session.commit()
        agenda_summary_timings[AGENDA_SUMMARY_PERSIST_MS] += _elapsed_millis(commit_started_at)

    reindex_summary = _time_reindex_callback(agenda_summary_timings, changed_catalog_ids, reindex_callback)
    embed_summary = _time_embed_callback(agenda_summary_timings, changed_catalog_ids, embed_callback)

    return {
        "results": results,
        "changed_catalog_ids": changed_catalog_ids,
        "reindex_summary": reindex_summary,
        "embed_summary": embed_summary,
        "agenda_summary_timings": _rounded_agenda_summary_timings(agenda_summary_timings),
    }


def _provider_failure_detected(result: dict[str, Any], fallback_events: dict[str, int]) -> bool:
    if fallback_events.get("timeout", 0) or fallback_events.get("unavailable", 0):
        return True
    lowered_error = str(result.get("error") or "").lower()
    return any(token in lowered_error for token in _PROVIDER_FAILURE_TOKENS)


def summarize_catalog_with_optional_fallback(
    catalog_id: int,
    *,
    summary_fallback_mode: str = "none",
    generate_summary_callable: Callable[[int], dict[str, Any] | None],
    deterministic_summary_callable: Callable[[int], dict[str, Any]],
    capture_summary_fallback_events_factory: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    fallback_context = (
        capture_summary_fallback_events_factory()
        if capture_summary_fallback_events_factory is not None
        else nullcontext({})
    )
    with fallback_context as fallback_events:
        try:
            result = generate_summary_callable(catalog_id) or {}
        except AGENDA_SUMMARY_CALLABLE_ERRORS as error:
            result = {"status": "error", "error": str(error)}

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
    session_factory: Callable[[], Any] = db_session,
    capture_summary_fallback_events_factory: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    with session_factory() as session:
        document = session.query(Document).filter_by(catalog_id=catalog_id).first()
        doc_kind = normalize_summary_doc_kind(document.category if document else "unknown")

    if doc_kind == "agenda":
        try:
            result = deterministic_summary_callable(catalog_id)
        except AGENDA_SUMMARY_CALLABLE_ERRORS as error:
            return {"status": "error", "error": str(error)}
        if str(result.get("status") or "other") == "complete":
            result["completion_mode"] = "agenda_deterministic"
        return result

    return summarize_catalog_with_optional_fallback(
        catalog_id,
        summary_fallback_mode=summary_fallback_mode,
        generate_summary_callable=generate_summary_callable,
        deterministic_summary_callable=deterministic_summary_callable,
        capture_summary_fallback_events_factory=capture_summary_fallback_events_factory,
    )

from __future__ import annotations

from contextlib import nullcontext
from typing import Any, Callable

from pipeline.agenda_summary_contracts import AGENDA_SUMMARY_CALLABLE_ERRORS, AgendaSummaryPayload
from pipeline.db_session import db_session
from pipeline.document_kinds import normalize_summary_doc_kind
from pipeline.models import Document

_PROVIDER_FAILURE_TOKENS = ("timed out", "timeout", "unavailable", "connection", "empty response payload")


def summarize_catalog_with_optional_fallback(
    catalog_id: int,
    *,
    summary_fallback_mode: str = "none",
    generate_summary_callable: Callable[[int], dict[str, Any] | None],
    deterministic_summary_callable: Callable[[int], dict[str, Any]],
    capture_summary_fallback_events_factory: Callable[[], Any] | None = None,
) -> AgendaSummaryPayload:
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
    optional_fallback_callable: Callable[..., AgendaSummaryPayload] = summarize_catalog_with_optional_fallback,
) -> AgendaSummaryPayload:
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

    return optional_fallback_callable(
        catalog_id,
        summary_fallback_mode=summary_fallback_mode,
        generate_summary_callable=generate_summary_callable,
        deterministic_summary_callable=deterministic_summary_callable,
        capture_summary_fallback_events_factory=capture_summary_fallback_events_factory,
    )


def _provider_failure_detected(result: dict[str, Any], fallback_events: dict[str, int]) -> bool:
    if (
        fallback_events.get("timeout", 0)
        or fallback_events.get("unavailable", 0)
        or fallback_events.get("empty_response", 0)
    ):
        return True
    lowered_error = str(result.get("error") or "").lower()
    return any(token in lowered_error for token in _PROVIDER_FAILURE_TOKENS)

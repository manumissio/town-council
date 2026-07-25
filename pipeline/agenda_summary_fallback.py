from __future__ import annotations

from typing import Any

from pipeline import (
    agenda_segmentation_maintenance,
    agenda_summary_batch,
    non_agenda_summary_fallback,
    task_runtime,
    task_summary_generation,
)
from pipeline.agenda_summary_contracts import AGENDA_SUMMARY_CALLABLE_ERRORS, AgendaSummaryPayload
from pipeline.db_session import db_session
from pipeline.document_kinds import normalize_summary_doc_kind
from pipeline.local_ai_runtime import LocalAIConfigError
from pipeline.models import Document
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

_PROVIDER_FAILURE_REASONS = (
    ("empty_response", ("empty response payload",)),
    ("timeout", ("timed out", "timeout")),
    ("unavailable", ("unavailable", "connection")),
)


def summarize_catalog_with_optional_fallback(
    catalog_id: int,
    *,
    force: bool = False,
    summary_fallback_mode: str = "none",
) -> AgendaSummaryPayload:
    with agenda_segmentation_maintenance.capture_summary_fallback_events() as fallback_events:
        try:
            result = _generate_catalog_summary(catalog_id, force=force) or {}
        except LocalAIConfigError as config_error:
            return {"status": "error", "error": str(config_error)}
        except AGENDA_SUMMARY_CALLABLE_ERRORS as error:
            result = {"status": "error", "error": str(error)}

    status = str(result.get("status") or "other")
    fallback_reason = _provider_failure_reason(result, fallback_events)
    if summary_fallback_mode == "deterministic" and status == "error" and fallback_reason:
        fallback_result = (
            non_agenda_summary_fallback.build_deterministic_non_agenda_summary_payload(
                catalog_id,
                fallback_reason=fallback_reason,
            )
        )
        fallback_result["provider_failure"] = dict(fallback_events)
        return fallback_result
    if status == "complete":
        result["completion_mode"] = "llm"
    return result


def summarize_catalog_with_maintenance_mode(
    catalog_id: int,
    *,
    force: bool = False,
    summary_fallback_mode: str = "none",
) -> AgendaSummaryPayload:
    with db_session() as session:
        document = session.query(Document).filter_by(catalog_id=catalog_id).first()
        doc_kind = normalize_summary_doc_kind(document.category if document else "unknown")

    if doc_kind == "agenda":
        try:
            result = agenda_summary_batch.build_deterministic_agenda_summary_payload(
                catalog_id
            )
        except AGENDA_SUMMARY_CALLABLE_ERRORS as error:
            return {"status": "error", "error": str(error)}
        if str(result.get("status") or "other") == "complete":
            result["completion_mode"] = "agenda_deterministic"
        return result

    return summarize_catalog_with_optional_fallback(
        catalog_id,
        force=force,
        summary_fallback_mode=summary_fallback_mode,
    )


def _generate_catalog_summary(
    catalog_id: int,
    *,
    force: bool,
) -> dict[str, Any]:
    db: Session = task_runtime.task_session()
    try:
        return task_summary_generation.generate_catalog_summary(
            db,
            catalog_id,
            force=force,
        )
    except LocalAIConfigError as config_error:
        task_runtime.logger.critical(
            "LocalAI misconfiguration catalog_id=%s error=%s",
            catalog_id,
            config_error,
        )
        db.rollback()
        raise
    except (SQLAlchemyError, RuntimeError, ValueError):
        db.rollback()
        raise
    finally:
        db.close()


def _provider_failure_reason(result: dict[str, Any], fallback_events: dict[str, int]) -> str | None:
    for reason, _tokens in _PROVIDER_FAILURE_REASONS:
        if fallback_events.get(reason, 0):
            return reason
    lowered_error = str(result.get("error") or "").lower()
    for reason, tokens in _PROVIDER_FAILURE_REASONS:
        if any(token in lowered_error for token in tokens):
            return reason
    return None

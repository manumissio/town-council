from __future__ import annotations

from typing import Any

from pipeline.agenda_summary_batch import persist_agenda_summary
from pipeline.llm import LocalAI
from pipeline.models import Catalog
from pipeline.summary_freshness import compute_summary_source_hash
from pipeline.summary_grounding import is_summary_grounded
from pipeline.task_summary_generation_contracts import (
    AGENDA_DOC_KIND,
    SUMMARY_BLOCKED_UNGROUNDED_STATUS,
    SUMMARY_COMPLETE_STATUS,
    SUMMARY_NONE_RETRY_ERROR,
    PreparedSummaryInput,
    SummaryRecordContext,
    SummaryTaskContext,
)
from pipeline.task_summary_side_effects import run_summary_generation_side_effects
from pipeline.text_cleaning import postprocess_extracted_text


def _generated_summary(
    *,
    local_ai: LocalAI,
    doc_kind: str,
    catalog: Catalog,
    agenda_summary_bundle: dict[str, Any] | None,
) -> tuple[str | None, bool]:
    if doc_kind == AGENDA_DOC_KIND:
        if agenda_summary_bundle is None:
            raise RuntimeError("Agenda summary bundle is required for agenda summaries")
        summary = local_ai.summarize_agenda_items(
            meeting_title=agenda_summary_bundle["meeting_title"],
            meeting_date=agenda_summary_bundle["meeting_date"],
            items=agenda_summary_bundle["summary_items"],
            truncation_meta=agenda_summary_bundle["truncation_meta"],
        )
        # Agenda summaries are derived from structured titles, not raw text.
        return summary, False

    return local_ai.summarize(
        postprocess_extracted_text(catalog.content),
        doc_kind=doc_kind,
    ), True


def _ungrounded_summary_payload(
    *,
    summary: str,
    catalog: Catalog,
) -> dict[str, Any] | None:
    grounding = is_summary_grounded(summary, postprocess_extracted_text(catalog.content))
    if grounding.is_grounded:
        return None

    reason = (
        "Generated summary appears unsupported by extracted text. "
        f"(coverage={grounding.coverage:.2f})"
    )
    return {
        "status": SUMMARY_BLOCKED_UNGROUNDED_STATUS,
        "reason": reason,
        "unsupported_claims": grounding.unsupported_claims[:3],
        "summary": None,
    }


def _persist_non_agenda_summary(
    *,
    catalog: Catalog,
    summary: str,
    doc_kind: str,
    content_hash: str | None,
    agenda_items_hash: str | None,
) -> dict[str, Any]:
    prior_summary = catalog.summary
    prior_summary_source_hash = catalog.summary_source_hash
    summary_source_hash = compute_summary_source_hash(
        doc_kind,
        content_hash=content_hash,
        agenda_items_hash=agenda_items_hash,
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


def _persist_generated_summary(
    context: SummaryTaskContext,
    record: SummaryRecordContext,
    prepared: PreparedSummaryInput,
    summary: str,
) -> dict[str, Any]:
    if record.doc_kind == AGENDA_DOC_KIND:
        if prepared.agenda_summary_bundle is None:
            raise RuntimeError("Agenda summary bundle is required for agenda summary persistence")
        return persist_agenda_summary(
            catalog=record.catalog,
            summary=summary,
            content_hash=prepared.agenda_summary_bundle["content_hash"],
            agenda_items_hash=prepared.agenda_summary_bundle["agenda_items_hash"],
            agenda_segmentation_status=getattr(record.catalog, "agenda_segmentation_status", None),
        )
    return _persist_non_agenda_summary(
        catalog=record.catalog,
        summary=summary,
        doc_kind=record.doc_kind,
        content_hash=record.content_hash,
        agenda_items_hash=prepared.agenda_items_hash,
    )


def generate_and_persist_summary(
    context: SummaryTaskContext,
    record: SummaryRecordContext,
    prepared: PreparedSummaryInput,
) -> dict[str, Any]:
    local_ai = LocalAI()
    summary, do_grounding_check = _generated_summary(
        local_ai=local_ai,
        doc_kind=record.doc_kind,
        catalog=record.catalog,
        agenda_summary_bundle=prepared.agenda_summary_bundle,
    )
    if summary is None:
        raise RuntimeError(SUMMARY_NONE_RETRY_ERROR)
    if do_grounding_check:
        grounding_payload = _ungrounded_summary_payload(summary=summary, catalog=record.catalog)
        if grounding_payload is not None:
            return grounding_payload

    persisted_summary = _persist_generated_summary(context, record, prepared, summary)
    context.db.commit()
    side_effects = run_summary_generation_side_effects(context.catalog_id)
    return {
        "status": SUMMARY_COMPLETE_STATUS,
        "summary": summary,
        "changed": bool(persisted_summary["changed"]),
        **side_effects,
    }

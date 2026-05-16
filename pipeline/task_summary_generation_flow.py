from __future__ import annotations

from typing import Any

from pipeline.agenda_summary_empty import is_empty_agenda_without_items
from pipeline.models import AgendaItem, Catalog, Document
from pipeline.task_summary_empty_agenda import EmptyAgendaGenerationContext, run_empty_agenda_generation
from pipeline.task_summary_generation_contracts import (
    AGENDA_DOC_KIND,
    SUMMARY_BLOCKED_LOW_SIGNAL_STATUS,
    SUMMARY_CACHED_STATUS,
    SUMMARY_ERROR_STATUS,
    SUMMARY_STALE_STATUS,
    PreparedSummaryInput,
    SummaryGenerationTaskServices,
    SummaryRecordContext,
    SummaryTaskContext,
)
from pipeline.task_summary_generation_persistence import generate_and_persist_summary
from pipeline.task_summary_side_effects import run_summary_generation_side_effects


def _source_text_quality_payload(catalog: Catalog, services: SummaryGenerationTaskServices) -> dict[str, Any] | None:
    if not catalog.content:
        return {"error": "No content to summarize"}

    quality = services.analyze_source_text(catalog.content)
    if services.is_source_summarizable(quality):
        return None

    # We do not run Gemma on low-signal content because it tends to hallucinate.
    return {
        "status": SUMMARY_BLOCKED_LOW_SIGNAL_STATUS,
        "reason": services.build_low_signal_message(quality),
        "summary": None,
    }


def _agenda_summary_bundle(
    *,
    catalog: Catalog,
    document: Document | None,
    agenda_items: list[AgendaItem],
    services: SummaryGenerationTaskServices,
) -> dict[str, Any]:
    return services.build_agenda_summary_input_bundle(
        catalog=catalog,
        document=document,
        agenda_items=agenda_items,
        include_meeting_context=True,
    )


def _agenda_items_for_catalog(db: Any, catalog_id: int) -> list[AgendaItem]:
    return (
        db.query(AgendaItem)
        .filter_by(catalog_id=catalog_id)
        .order_by(AgendaItem.order)
        .all()
    )


def _stale_or_cached_summary_payload(
    *,
    force: bool,
    is_fresh: bool,
    summary: str | None,
) -> dict[str, Any] | None:
    if (not force) and is_fresh:
        return {"status": SUMMARY_CACHED_STATUS, "summary": summary, "changed": False}
    if (not force) and summary and not is_fresh:
        # Keep the old summary visible, but mark it as out-of-date.
        return {"status": SUMMARY_STALE_STATUS, "summary": summary, "changed": False}
    return None


def _load_summary_record(context: SummaryTaskContext) -> SummaryRecordContext | dict[str, Any]:
    catalog = context.db.get(Catalog, context.catalog_id)
    document = context.db.query(Document).filter_by(catalog_id=context.catalog_id).first()
    doc_kind = context.services.normalize_summary_doc_kind(document.category if document else "unknown")
    if not catalog:
        return {"error": "Catalog not found"}

    classification = context.services.classify_catalog_bad_content(catalog)
    if classification:
        return {"status": SUMMARY_ERROR_STATUS, "error": classification.reason}

    content_hash = context.services.compute_content_hash(catalog.content) if (catalog.content or "") else None
    if content_hash:
        catalog.content_hash = content_hash
    return SummaryRecordContext(catalog, document, doc_kind, content_hash)


def _prepare_agenda_summary_input(
    context: SummaryTaskContext,
    record: SummaryRecordContext,
) -> PreparedSummaryInput | dict[str, Any]:
    agenda_items = _agenda_items_for_catalog(context.db, context.catalog_id)
    if is_empty_agenda_without_items(record.catalog, agenda_items):
        return run_empty_agenda_generation(
            EmptyAgendaGenerationContext(
                db=context.db,
                catalog_id=context.catalog_id,
                force=context.force,
                catalog=record.catalog,
                content_hash=record.content_hash,
                services=context.services,
                side_effects_runner=lambda selected_catalog_id: run_summary_generation_side_effects(
                    selected_catalog_id,
                    services=context.services,
                ),
            )
        )

    agenda_summary_bundle = _agenda_summary_bundle(
        catalog=record.catalog,
        document=record.document,
        agenda_items=agenda_items,
        services=context.services,
    )
    if agenda_summary_bundle.get("status") != "ready":
        return agenda_summary_bundle

    agenda_items_hash = agenda_summary_bundle["agenda_items_hash"]
    if agenda_items_hash != record.catalog.agenda_items_hash:
        record.catalog.agenda_items_hash = agenda_items_hash
    return PreparedSummaryInput(agenda_items_hash, agenda_summary_bundle)


def _prepare_summary_input(
    context: SummaryTaskContext,
    record: SummaryRecordContext,
) -> PreparedSummaryInput | dict[str, Any]:
    if record.doc_kind != AGENDA_DOC_KIND:
        quality_payload = _source_text_quality_payload(record.catalog, context.services)
        if quality_payload is not None:
            return quality_payload
        return PreparedSummaryInput(record.catalog.agenda_items_hash, None)
    return _prepare_agenda_summary_input(context, record)


def _cached_summary_payload(
    context: SummaryTaskContext,
    record: SummaryRecordContext,
    prepared: PreparedSummaryInput,
) -> dict[str, Any] | None:
    is_fresh = context.services.is_summary_fresh(
        record.doc_kind,
        summary=record.catalog.summary,
        summary_source_hash=record.catalog.summary_source_hash,
        content_hash=record.content_hash,
        agenda_items_hash=prepared.agenda_items_hash,
        agenda_segmentation_status=getattr(record.catalog, "agenda_segmentation_status", None),
    )
    return _stale_or_cached_summary_payload(
        force=context.force,
        is_fresh=is_fresh,
        summary=record.catalog.summary,
    )


def run_generate_summary_task_family(
    db: Any,
    catalog_id: int,
    *,
    force: bool,
    services: SummaryGenerationTaskServices,
) -> dict[str, Any]:
    context = SummaryTaskContext(db, catalog_id, force, services)
    record = _load_summary_record(context)
    if isinstance(record, dict):
        return record

    prepared = _prepare_summary_input(context, record)
    if isinstance(prepared, dict):
        return prepared

    cached_payload = _cached_summary_payload(context, record, prepared)
    if cached_payload is not None:
        return cached_payload

    return generate_and_persist_summary(context, record, prepared)

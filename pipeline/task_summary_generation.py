from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pipeline.llm import LocalAI
from pipeline.models import AgendaItem, Catalog, Document
from pipeline.task_summary_side_effects import run_summary_generation_side_effects


AGENDA_DOC_KIND = "agenda"
SUMMARY_COMPLETE_STATUS = "complete"
SUMMARY_CACHED_STATUS = "cached"
SUMMARY_STALE_STATUS = "stale"
SUMMARY_ERROR_STATUS = "error"
SUMMARY_BLOCKED_LOW_SIGNAL_STATUS = "blocked_low_signal"
SUMMARY_BLOCKED_UNGROUNDED_STATUS = "blocked_ungrounded"
SUMMARY_NONE_RETRY_ERROR = "AI Summarization returned None (Model missing or error)"


@dataclass(frozen=True)
class SummaryGenerationTaskServices:
    local_ai_factory: Callable[[], LocalAI]
    classify_catalog_bad_content: Callable[..., object]
    compute_content_hash: Callable[[str | None], str | None]
    normalize_summary_doc_kind: Callable[[str], str]
    analyze_source_text: Callable[[str], object]
    is_source_summarizable: Callable[[object], bool]
    build_low_signal_message: Callable[[object], str]
    build_agenda_summary_input_bundle: Callable[..., dict[str, Any]]
    is_summary_fresh: Callable[..., bool]
    compute_summary_source_hash: Callable[..., str | None]
    postprocess_extracted_text: Callable[[str | None], str]
    is_summary_grounded: Callable[[str, str], object]
    persist_agenda_summary: Callable[..., dict[str, Any]]
    reindex_catalog: Callable[[int], object]
    embed_catalog: Callable[[int], object]

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
    db,
    *,
    catalog: Catalog,
    document: Document | None,
    catalog_id: int,
    services: SummaryGenerationTaskServices,
) -> dict[str, Any]:
    return services.build_agenda_summary_input_bundle(
        catalog=catalog,
        document=document,
        agenda_items=(
            db.query(AgendaItem)
            .filter_by(catalog_id=catalog_id)
            .order_by(AgendaItem.order)
            .all()
        ),
        include_meeting_context=True,
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


def _generated_summary(
    *,
    local_ai: LocalAI,
    doc_kind: str,
    catalog: Catalog,
    agenda_summary_bundle: dict[str, Any] | None,
    services: SummaryGenerationTaskServices,
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
        services.postprocess_extracted_text(catalog.content),
        doc_kind=doc_kind,
    ), True


def _ungrounded_summary_payload(
    *,
    summary: str,
    catalog: Catalog,
    services: SummaryGenerationTaskServices,
) -> dict[str, Any] | None:
    grounding = services.is_summary_grounded(summary, services.postprocess_extracted_text(catalog.content))
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
    services: SummaryGenerationTaskServices,
) -> dict[str, Any]:
    prior_summary = catalog.summary
    prior_summary_source_hash = catalog.summary_source_hash
    summary_source_hash = services.compute_summary_source_hash(
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


def run_generate_summary_task_family(
    db,
    catalog_id: int,
    *,
    force: bool,
    services: SummaryGenerationTaskServices,
) -> dict[str, Any]:
    """
    Run summary generation for one catalog while leaving retry and session ownership to the task.
    """
    catalog = db.get(Catalog, catalog_id)

    doc = db.query(Document).filter_by(catalog_id=catalog_id).first()
    doc_kind = services.normalize_summary_doc_kind(doc.category if doc else "unknown")

    if not catalog:
        return {"error": "Catalog not found"}
    classification = services.classify_catalog_bad_content(catalog)
    if classification:
        return {"status": SUMMARY_ERROR_STATUS, "error": classification.reason}
    local_ai = services.local_ai_factory()

    content_hash = services.compute_content_hash(catalog.content) if (catalog.content or "") else None
    if content_hash:
        catalog.content_hash = content_hash

    if doc_kind != AGENDA_DOC_KIND:
        quality_payload = _source_text_quality_payload(catalog, services)
        if quality_payload is not None:
            return quality_payload

    agenda_items_hash = catalog.agenda_items_hash
    agenda_summary_bundle = None
    if doc_kind == AGENDA_DOC_KIND:
        agenda_summary_bundle = _agenda_summary_bundle(
            db,
            catalog=catalog,
            document=doc,
            catalog_id=catalog_id,
            services=services,
        )
        if agenda_summary_bundle.get("status") != "ready":
            return agenda_summary_bundle
        agenda_items_hash = agenda_summary_bundle["agenda_items_hash"]
        if agenda_items_hash != catalog.agenda_items_hash:
            catalog.agenda_items_hash = agenda_items_hash

    is_fresh = services.is_summary_fresh(
        doc_kind,
        summary=catalog.summary,
        summary_source_hash=catalog.summary_source_hash,
        content_hash=content_hash,
        agenda_items_hash=agenda_items_hash,
    )
    cached_payload = _stale_or_cached_summary_payload(
        force=force,
        is_fresh=is_fresh,
        summary=catalog.summary,
    )
    if cached_payload is not None:
        return cached_payload

    summary, do_grounding_check = _generated_summary(
        local_ai=local_ai,
        doc_kind=doc_kind,
        catalog=catalog,
        agenda_summary_bundle=agenda_summary_bundle,
        services=services,
    )
    if summary is None:
        raise RuntimeError(SUMMARY_NONE_RETRY_ERROR)

    if do_grounding_check:
        grounding_payload = _ungrounded_summary_payload(summary=summary, catalog=catalog, services=services)
        if grounding_payload is not None:
            return grounding_payload

    if doc_kind == AGENDA_DOC_KIND:
        if agenda_summary_bundle is None:
            raise RuntimeError("Agenda summary bundle is required for agenda summary persistence")
        persisted_summary = services.persist_agenda_summary(
            catalog=catalog,
            summary=summary,
            content_hash=agenda_summary_bundle["content_hash"],
            agenda_items_hash=agenda_summary_bundle["agenda_items_hash"],
        )
    else:
        persisted_summary = _persist_non_agenda_summary(
            catalog=catalog,
            summary=summary,
            doc_kind=doc_kind,
            content_hash=content_hash,
            agenda_items_hash=agenda_items_hash,
            services=services,
        )
    db.commit()

    side_effects = run_summary_generation_side_effects(catalog_id, services=services)
    return {
        "status": SUMMARY_COMPLETE_STATUS,
        "summary": summary,
        "changed": bool(persisted_summary["changed"]),
        **side_effects,
    }

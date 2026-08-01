from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session as SQLAlchemySession

from api import catalog_summary_state, task_dispatch
from pipeline import summary_freshness, summary_quality
from pipeline.agenda_summary_empty import EMPTY_AGENDA_SEGMENTATION_STATUS
from pipeline.models import Catalog

AGENDA_DOC_KIND = "agenda"


@dataclass(frozen=True, slots=True)
class SummaryFreshnessContext:
    force: bool
    catalog: Catalog
    doc_kind: str
    content_hash: str | None
    agenda_items_hash: str | None
    agenda_segmentation_status: str | None


def _is_empty_agenda_summary_candidate(
    *,
    doc_kind: str,
    agenda_segmentation_status: str | None,
    agenda_items_hash: str | None,
) -> bool:
    return (
        doc_kind == AGENDA_DOC_KIND
        and agenda_segmentation_status == EMPTY_AGENDA_SEGMENTATION_STATUS
        and agenda_items_hash is None
    )


def _summary_freshness_payload(
    *,
    freshness_context: SummaryFreshnessContext,
) -> dict[str, Any] | None:
    is_fresh = summary_freshness.is_summary_fresh(
        freshness_context.doc_kind,
        summary=freshness_context.catalog.summary,
        summary_source_hash=freshness_context.catalog.summary_source_hash,
        content_hash=freshness_context.content_hash,
        agenda_items_hash=freshness_context.agenda_items_hash,
        agenda_segmentation_status=freshness_context.agenda_segmentation_status,
    )
    if (not freshness_context.force) and is_fresh:
        return {"summary": freshness_context.catalog.summary, "status": "cached"}
    if (not freshness_context.force) and freshness_context.catalog.summary and not is_fresh:
        return {"summary": freshness_context.catalog.summary, "status": "stale"}
    return None


def _enqueue_summary_task(*, catalog_id: int, force: bool) -> dict[str, Any]:
    task_id = task_dispatch.enqueue_task(
        task_dispatch.GENERATE_SUMMARY_OPERATION_KEY,
        task_dispatch.GENERATE_SUMMARY_TASK_NAME,
        catalog_id,
        force=force,
    )
    return {
        "status": "processing",
        "task_id": task_id,
        "poll_url": f"/tasks/{task_id}",
    }


def summarize_document_request(
    *,
    db: SQLAlchemySession,
    catalog_id: int,
    force: bool,
) -> dict[str, Any]:
    catalog = db.get(Catalog, catalog_id)
    if not catalog:
        raise HTTPException(status_code=404, detail="Document not found")
    if not catalog.content:
        raise HTTPException(status_code=400, detail="Document has no text to summarize")

    doc_kind, content_hash, agenda_items_hash = catalog_summary_state.resolve_summary_source_hashes(
        db,
        catalog_id,
        catalog,
    )
    agenda_segmentation_status = getattr(catalog, "agenda_segmentation_status", None)
    freshness_context = SummaryFreshnessContext(
        force=force,
        catalog=catalog,
        doc_kind=doc_kind,
        content_hash=content_hash,
        agenda_items_hash=agenda_items_hash,
        agenda_segmentation_status=agenda_segmentation_status,
    )

    if _is_empty_agenda_summary_candidate(
        doc_kind=doc_kind,
        agenda_segmentation_status=agenda_segmentation_status,
        agenda_items_hash=agenda_items_hash,
    ):
        freshness_payload = _summary_freshness_payload(
            freshness_context=freshness_context,
        )
        return freshness_payload or _enqueue_summary_task(catalog_id=catalog_id, force=force)

    quality = summary_quality.analyze_source_text(catalog.content)
    if not summary_quality.is_source_summarizable(quality):
        return {
            "status": "blocked_low_signal",
            "reason": summary_quality.build_low_signal_message(quality),
        }

    freshness_payload = _summary_freshness_payload(
        freshness_context=freshness_context,
    )
    return freshness_payload or _enqueue_summary_task(catalog_id=catalog_id, force=force)

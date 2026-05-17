from dataclasses import dataclass
from typing import Any, Callable

from fastapi import HTTPException

from pipeline.agenda_summary_empty import EMPTY_AGENDA_SEGMENTATION_STATUS

AGENDA_DOC_KIND = "agenda"
GENERATE_SUMMARY_TASK_KEY = "generate_summary_task"


@dataclass(frozen=True, slots=True)
class SummaryFreshnessContext:
    force: bool
    catalog: Any  # Existing route facade accepts SQLAlchemy rows and test doubles.
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
    is_summary_fresh: Callable[..., bool],
) -> dict[str, Any] | None:
    is_fresh = is_summary_fresh(
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


def _enqueue_summary_task(*, task_facade: Any, catalog_id: int, force: bool) -> dict[str, Any]:
    task_id = task_facade._enqueue_task(
        GENERATE_SUMMARY_TASK_KEY,
        task_facade.generate_summary_task,
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
    task_facade: Any,
    db: Any,
    catalog_id: int,
    force: bool,
    catalog_model: type[Any],
    analyze_source_text: Callable[[str], Any],
    build_low_signal_message: Callable[[Any], str],
    is_summary_fresh: Callable[..., bool],
    is_source_summarizable: Callable[[Any], bool],
) -> dict[str, Any]:
    catalog = db.get(catalog_model, catalog_id)
    if not catalog:
        raise HTTPException(status_code=404, detail="Document not found")
    if not catalog.content:
        raise HTTPException(status_code=400, detail="Document has no text to summarize")

    doc_kind, content_hash, agenda_items_hash = task_facade._summary_doc_kind_and_hashes(db, catalog_id, catalog)
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
            is_summary_fresh=is_summary_fresh,
        )
        return freshness_payload or _enqueue_summary_task(task_facade=task_facade, catalog_id=catalog_id, force=force)

    quality = analyze_source_text(catalog.content)
    if not is_source_summarizable(quality):
        return {
            "status": "blocked_low_signal",
            "reason": build_low_signal_message(quality),
        }

    freshness_payload = _summary_freshness_payload(
        freshness_context=freshness_context,
        is_summary_fresh=is_summary_fresh,
    )
    return freshness_payload or _enqueue_summary_task(task_facade=task_facade, catalog_id=catalog_id, force=force)

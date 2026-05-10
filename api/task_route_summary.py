from typing import Any, Callable

from fastapi import HTTPException


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

    quality = analyze_source_text(catalog.content)
    if not is_source_summarizable(quality):
        return {
            "status": "blocked_low_signal",
            "reason": build_low_signal_message(quality),
        }

    doc_kind, content_hash, agenda_items_hash = task_facade._summary_doc_kind_and_hashes(db, catalog_id, catalog)
    is_fresh = is_summary_fresh(
        doc_kind,
        summary=catalog.summary,
        summary_source_hash=catalog.summary_source_hash,
        content_hash=content_hash,
        agenda_items_hash=agenda_items_hash,
    )

    if (not force) and is_fresh:
        return {"summary": catalog.summary, "status": "cached"}
    if (not force) and catalog.summary and not is_fresh:
        return {"summary": catalog.summary, "status": "stale"}

    task_id = task_facade._enqueue_task(
        "generate_summary_task",
        task_facade.generate_summary_task,
        catalog_id,
        force=force,
    )
    return {
        "status": "processing",
        "task_id": task_id,
        "poll_url": f"/tasks/{task_id}",
    }

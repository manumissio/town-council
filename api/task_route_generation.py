from typing import Any, Callable

from fastapi import HTTPException


def extract_votes_request(
    *,
    task_facade: Any,
    db: Any,
    catalog_id: int,
    force: bool,
    catalog_model: type[Any],
) -> dict[str, str]:
    catalog = db.get(catalog_model, catalog_id)
    if not catalog:
        raise HTTPException(status_code=404, detail="Document not found")

    task_id = task_facade._enqueue_task("extract_votes_task", task_facade.extract_votes_task, catalog_id, force=force)
    return {
        "status": "processing",
        "task_id": task_id,
        "poll_url": f"/tasks/{task_id}",
    }


def generate_topics_request(
    *,
    task_facade: Any,
    db: Any,
    catalog_id: int,
    force: bool,
    catalog_model: type[Any],
    analyze_source_text: Callable[[str], Any],
    build_low_signal_message: Callable[[Any], str],
    compute_content_hash: Callable[[str], str],
    is_source_topicable: Callable[[Any], bool],
) -> dict[str, Any]:
    catalog = db.get(catalog_model, catalog_id)
    if not catalog:
        raise HTTPException(status_code=404, detail="Document not found")
    if not catalog.content:
        raise HTTPException(status_code=400, detail="Document has no text to tag")

    quality = analyze_source_text(catalog.content)
    if not is_source_topicable(quality):
        return {
            "status": "blocked_low_signal",
            "reason": build_low_signal_message(quality),
            "topics": [],
        }

    content_hash = catalog.content_hash or (compute_content_hash(catalog.content) if catalog.content else None)
    is_fresh = bool(
        catalog.topics is not None
        and content_hash
        and catalog.topics_source_hash
        and catalog.topics_source_hash == content_hash
    )
    if (not force) and is_fresh:
        return {"status": "cached", "topics": catalog.topics or []}
    if (not force) and catalog.topics is not None and not is_fresh:
        return {"status": "stale", "topics": catalog.topics or []}

    task_id = task_facade._enqueue_task(
        "generate_topics_task",
        task_facade.generate_topics_task,
        catalog_id,
        force=force,
    )
    return {
        "status": "processing",
        "task_id": task_id,
        "poll_url": f"/tasks/{task_id}",
    }


def extract_catalog_text_request(
    *,
    task_facade: Any,
    db: Any,
    catalog_id: int,
    force: bool,
    ocr_fallback: bool,
    catalog_model: type[Any],
    cached_content_min_chars: int,
) -> dict[str, Any]:
    catalog = db.get(catalog_model, catalog_id)
    if not catalog:
        raise HTTPException(status_code=404, detail="Document not found")

    if (not force) and catalog.content and len(catalog.content.strip()) >= cached_content_min_chars:
        return {"status": "cached", "catalog_id": catalog_id, "chars": len(catalog.content)}

    task_id = task_facade._enqueue_task(
        "extract_text_task",
        task_facade.extract_text_task,
        catalog_id,
        force=force,
        ocr_fallback=ocr_fallback,
    )
    return {
        "status": "processing",
        "task_id": task_id,
        "poll_url": f"/tasks/{task_id}",
    }

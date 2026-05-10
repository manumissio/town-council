import logging
from typing import Any

from fastapi import HTTPException


def segment_agenda_request(
    *,
    task_facade: Any,
    db: Any,
    catalog_id: int,
    force: bool,
    catalog_model: type[Any],
    agenda_item_model: type[Any],
    logger: logging.Logger,
) -> dict[str, Any]:
    catalog = db.get(catalog_model, catalog_id)
    if not catalog:
        raise HTTPException(status_code=404, detail="Document not found")

    existing_items = (
        db.query(agenda_item_model).filter_by(catalog_id=catalog_id).order_by(agenda_item_model.order).all()
    )
    if (
        not force
        and existing_items
        and task_facade.agenda_items_look_low_quality
        and not task_facade.agenda_items_look_low_quality(existing_items)
    ):
        return {"status": "cached", "items": existing_items}
    if not force and existing_items:
        logger.info(
            "Agenda cache for catalog_id=%s looks low quality; regenerating asynchronously.",
            catalog_id,
        )
    if force:
        logger.info("Force-regenerating agenda cache for catalog_id=%s.", catalog_id)

    task_id = task_facade._enqueue_task("segment_agenda_task", task_facade.segment_agenda_task, catalog_id)
    return {
        "status": "processing",
        "task_id": task_id,
        "poll_url": f"/tasks/{task_id}",
    }

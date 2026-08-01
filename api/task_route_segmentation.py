import logging
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session as SQLAlchemySession

from api import task_dispatch
from pipeline import agenda_resolver
from pipeline.models import AgendaItem, Catalog

logger = logging.getLogger("town-council-api")


def segment_agenda_request(
    *,
    db: SQLAlchemySession,
    catalog_id: int,
    force: bool,
) -> dict[str, Any]:
    catalog = db.get(Catalog, catalog_id)
    if not catalog:
        raise HTTPException(status_code=404, detail="Document not found")

    existing_items = (
        db.query(AgendaItem).filter_by(catalog_id=catalog_id).order_by(AgendaItem.order).all()
    )
    if (
        not force
        and existing_items
        and not agenda_resolver.agenda_items_look_low_quality(existing_items)
    ):
        return {"status": "cached", "items": existing_items}
    if not force and existing_items:
        logger.info(
            "Agenda cache for catalog_id=%s looks low quality; regenerating asynchronously.",
            catalog_id,
        )
    if force:
        logger.info("Force-regenerating agenda cache for catalog_id=%s.", catalog_id)

    task_id = task_dispatch.enqueue_task(
        task_dispatch.SEGMENT_AGENDA_OPERATION_KEY,
        task_dispatch.SEGMENT_AGENDA_TASK_NAME,
        catalog_id,
    )
    return {
        "status": "processing",
        "task_id": task_id,
        "poll_url": f"/tasks/{task_id}",
    }

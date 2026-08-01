import logging
import uuid
from typing import Any

from celery.result import AsyncResult
from fastapi import HTTPException

from api.task_dispatch import INVALID_TASK_ID_DETAIL
from pipeline.celery_app import app as celery_app

logger = logging.getLogger("town-council-api")


def get_task_status_payload(
    task_id: str,
) -> dict[str, Any]:
    try:
        uuid.UUID(task_id)
    except (ValueError, TypeError):
        logger.warning("Invalid task status request", extra={"task_id": task_id})
        raise HTTPException(status_code=400, detail=INVALID_TASK_ID_DETAIL)

    task = AsyncResult(task_id, app=celery_app)
    if not task.ready():
        return {"status": "processing"}

    task_payload = task.result
    if isinstance(task_payload, Exception):
        return {"status": "failed", "error": str(task_payload)}
    if isinstance(task_payload, dict) and "error" in task_payload:
        return {"status": "failed", "error": task_payload["error"]}

    return {
        "status": "complete",
        "result": task_payload,
    }

import logging
from typing import Any

from fastapi import HTTPException
from kombu.exceptions import KombuError

from pipeline.celery_app import app as celery_app

logger = logging.getLogger("town-council-api")

TASK_QUEUE_UNAVAILABLE_DETAIL = "Task queue unavailable"
INVALID_TASK_ID_DETAIL = "Invalid task_id format"
GENERATE_SUMMARY_TASK_NAME = "pipeline.tasks.generate_summary_task"
GENERATE_TOPICS_TASK_NAME = "enrichment.generate_topics"
SEGMENT_AGENDA_TASK_NAME = "pipeline.tasks.segment_agenda_task"
EXTRACT_VOTES_TASK_NAME = "pipeline.tasks.extract_votes_task"
EXTRACT_TEXT_TASK_NAME = "pipeline.tasks.extract_text_task"
GENERATE_SUMMARY_OPERATION_KEY = "generate_summary_task"
GENERATE_TOPICS_OPERATION_KEY = "generate_topics_task"
SEGMENT_AGENDA_OPERATION_KEY = "segment_agenda_task"
EXTRACT_VOTES_OPERATION_KEY = "extract_votes_task"
EXTRACT_TEXT_OPERATION_KEY = "extract_text_task"
TASK_DISPATCH_ERRORS = (KombuError, OSError, ConnectionError, TimeoutError)


def enqueue_task(
    operation_key: str,
    celery_task_name: str,
    *task_args: Any,
    **task_kwargs: Any,
) -> str:
    """
    Normalize broker/enqueue failures at the API boundary.
    """
    try:
        task = celery_app.send_task(celery_task_name, args=task_args, kwargs=task_kwargs)
    except TASK_DISPATCH_ERRORS as exc:
        logger.error(
            "Task enqueue failed",
            extra={"task_name": operation_key, "failure_class": exc.__class__.__name__},
            exc_info=True,
        )
        raise HTTPException(status_code=503, detail=TASK_QUEUE_UNAVAILABLE_DETAIL) from exc

    task_id = str(getattr(task, "id", "") or "").strip()
    if not task_id:
        logger.error(
            "Task enqueue returned missing task id",
            extra={"task_name": operation_key, "failure_class": "missing_task_id"},
        )
        raise HTTPException(status_code=503, detail=TASK_QUEUE_UNAVAILABLE_DETAIL)
    return task_id

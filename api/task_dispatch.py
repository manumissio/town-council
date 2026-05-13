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
TASK_DISPATCH_ERRORS = (KombuError, OSError, ConnectionError, TimeoutError)


class _CeleryTaskProxy:
    """
    Keep the API enqueue surface lightweight while preserving test patch points.
    """

    def __init__(self, task_name: str):
        self.name = task_name

    def delay(self, *args: Any, **kwargs: Any) -> Any:
        return celery_app.send_task(self.name, args=args, kwargs=kwargs)


generate_summary_task = _CeleryTaskProxy(GENERATE_SUMMARY_TASK_NAME)
generate_topics_task = _CeleryTaskProxy(GENERATE_TOPICS_TASK_NAME)
segment_agenda_task = _CeleryTaskProxy(SEGMENT_AGENDA_TASK_NAME)
extract_votes_task = _CeleryTaskProxy(EXTRACT_VOTES_TASK_NAME)
extract_text_task = _CeleryTaskProxy(EXTRACT_TEXT_TASK_NAME)


def _enqueue_task(task_name: str, task_callable: Any, *task_args: Any, **task_kwargs: Any) -> str:
    """
    Normalize broker/enqueue failures at the API boundary.
    """
    try:
        task = task_callable.delay(*task_args, **task_kwargs)
    except TASK_DISPATCH_ERRORS as exc:
        logger.error(
            "Task enqueue failed",
            extra={"task_name": task_name, "failure_class": exc.__class__.__name__},
            exc_info=True,
        )
        raise HTTPException(status_code=503, detail=TASK_QUEUE_UNAVAILABLE_DETAIL) from exc

    task_id = str(getattr(task, "id", "") or "").strip()
    if not task_id:
        logger.error(
            "Task enqueue returned missing task id",
            extra={"task_name": task_name, "failure_class": "missing_task_id"},
        )
        raise HTTPException(status_code=503, detail=TASK_QUEUE_UNAVAILABLE_DETAIL)
    return task_id

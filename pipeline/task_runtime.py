import logging

from sqlalchemy.orm import sessionmaker

from pipeline.models import db_connect


TASK_LOGGER_NAME = "celery-worker"

logger = logging.getLogger(TASK_LOGGER_NAME)

_session_factory = None


def task_session():
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(bind=db_connect())
    return _session_factory()

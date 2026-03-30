import os

from celery import Celery
from kombu import Queue


app = Celery("tasks")
app.conf.broker_url = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")
app.conf.result_backend = os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/0")
app.conf.task_default_queue = "celery"
app.conf.task_queues = (
    Queue("celery"),
    Queue("enrichment"),
    Queue("semantic"),
)
app.conf.task_routes = {
    "enrichment.generate_topics": {"queue": "enrichment"},
    "semantic.embed_catalog": {"queue": "semantic"},
}

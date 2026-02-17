"""
Prometheus metrics for background workers (Celery).

Important constraint:
The worker runs with a single-process pool (solo) in docker-compose so that the
metrics HTTP endpoint can expose task timings from the same process that
executes tasks. If the worker used a prefork pool, each child would have its own
in-memory metrics, and the endpoint would only report the parent's values.
"""

from __future__ import annotations

import os
import time
from typing import Dict

from celery import signals
from prometheus_client import Counter, Histogram, start_http_server


CELERY_TASK_DURATION_SECONDS = Histogram(
    "tc_celery_task_duration_seconds",
    "Celery task runtime in seconds.",
    labelnames=("task_name", "status"),
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60, 120),
)

CELERY_TASK_FAILURES_TOTAL = Counter(
    "tc_celery_task_failures_total",
    "Total number of Celery task failures.",
    labelnames=("task_name", "exception_type"),
)

CELERY_TASK_RETRIES_TOTAL = Counter(
    "tc_celery_task_retries_total",
    "Total number of Celery task retries.",
    labelnames=("task_name",),
)

LINEAGE_RECOMPUTE_RUNS_TOTAL = Counter(
    "tc_lineage_recompute_runs_total",
    "Total lineage recompute runs executed by Celery.",
)

LINEAGE_CATALOG_UPDATES_TOTAL = Counter(
    "tc_lineage_catalog_updates_total",
    "Total catalog lineage rows updated by lineage recompute.",
)

LINEAGE_COMPONENT_MERGES_TOTAL = Counter(
    "tc_lineage_component_merges_total",
    "Total connected-component lineage merges observed during recompute.",
)


_TASK_START: Dict[str, float] = {}


def record_task_duration(task_name: str, status: str, duration_s: float) -> None:
    CELERY_TASK_DURATION_SECONDS.labels(task_name=task_name, status=status).observe(max(0.0, duration_s))


def record_task_failure(task_name: str, exception_type: str) -> None:
    CELERY_TASK_FAILURES_TOTAL.labels(task_name=task_name, exception_type=exception_type).inc()


def record_task_retry(task_name: str) -> None:
    CELERY_TASK_RETRIES_TOTAL.labels(task_name=task_name).inc()


def record_lineage_recompute(updated_count: int, merge_count: int) -> None:
    LINEAGE_RECOMPUTE_RUNS_TOTAL.inc()
    if updated_count > 0:
        LINEAGE_CATALOG_UPDATES_TOTAL.inc(updated_count)
    if merge_count > 0:
        LINEAGE_COMPONENT_MERGES_TOTAL.inc(merge_count)


@signals.worker_ready.connect
def _start_metrics_server(**_kwargs):
    port = os.getenv("TC_WORKER_METRICS_PORT")
    if not port:
        return
    try:
        start_http_server(int(port))
    except Exception:
        # If the port is already in use or invalid, we fail soft; observability
        # shouldn't crash the worker.
        return


@signals.task_prerun.connect
def _task_prerun(task_id=None, task=None, **_kwargs):
    if task_id and task is not None:
        _TASK_START[str(task_id)] = time.perf_counter()


@signals.task_postrun.connect
def _task_postrun(task_id=None, task=None, state=None, **_kwargs):
    if not task_id or task is None:
        return
    start = _TASK_START.pop(str(task_id), None)
    if start is None:
        return
    status = "success" if (state or "").lower() in ("success", "succeeded") else "unknown"
    record_task_duration(getattr(task, "name", "unknown"), status, time.perf_counter() - start)


@signals.task_failure.connect
def _task_failure(task_id=None, exception=None, sender=None, **_kwargs):
    task_name = getattr(sender, "name", "unknown")
    exc_type = type(exception).__name__ if exception is not None else "Exception"
    record_task_failure(task_name, exc_type)

    if task_id:
        start = _TASK_START.pop(str(task_id), None)
        if start is not None:
            record_task_duration(task_name, "failure", time.perf_counter() - start)


@signals.task_retry.connect
def _task_retry(request=None, **_kwargs):
    task_name = getattr(getattr(request, "task", None), "name", None) or getattr(request, "task_name", None) or "unknown"
    record_task_retry(str(task_name))

from __future__ import annotations

from pipeline import metrics_definitions
from pipeline.profiling import profile_observer


def record_task_duration(task_name: str, status: str, duration_s: float) -> None:
    metrics_definitions.CELERY_TASK_DURATION_SECONDS.labels(
        task_name=task_name,
        status=status,
    ).observe(max(0.0, duration_s))


def record_task_failure(task_name: str, exception_type: str) -> None:
    metrics_definitions.CELERY_TASK_FAILURES_TOTAL.labels(
        task_name=task_name,
        exception_type=exception_type,
    ).inc()


def record_task_retry(task_name: str) -> None:
    metrics_definitions.CELERY_TASK_RETRIES_TOTAL.labels(task_name=task_name).inc()


def record_task_queue_wait(task_name: str, queue: str, duration_s: float) -> None:
    metrics_definitions.TASK_QUEUE_WAIT_SECONDS.labels(
        task_name=task_name,
        queue=queue,
    ).observe(max(0.0, duration_s))


def record_pipeline_phase_duration(phase: str, component: str, mode: str, status: str, duration_s: float) -> None:
    with profile_observer():
        metrics_definitions.PIPELINE_PHASE_DURATION_SECONDS.labels(
            phase=phase,
            component=component,
            mode=mode,
            status=status,
        ).observe(max(0.0, duration_s))


def record_lineage_recompute(updated_count: int, merge_count: int) -> None:
    metrics_definitions.LINEAGE_RECOMPUTE_RUNS_TOTAL.inc()
    if updated_count > 0:
        metrics_definitions.LINEAGE_CATALOG_UPDATES_TOTAL.inc(updated_count)
    if merge_count > 0:
        metrics_definitions.LINEAGE_COMPONENT_MERGES_TOTAL.inc(merge_count)

from __future__ import annotations

import sys

from pipeline import metrics_definitions


def _facade_metric(metric_name: str) -> object:
    metrics_facade = sys.modules.get("pipeline.metrics")
    return getattr(metrics_facade, metric_name, getattr(metrics_definitions, metric_name))


def record_task_duration(task_name: str, status: str, duration_s: float) -> None:
    _facade_metric("CELERY_TASK_DURATION_SECONDS").labels(task_name=task_name, status=status).observe(max(0.0, duration_s))


def record_task_failure(task_name: str, exception_type: str) -> None:
    _facade_metric("CELERY_TASK_FAILURES_TOTAL").labels(task_name=task_name, exception_type=exception_type).inc()


def record_task_retry(task_name: str) -> None:
    _facade_metric("CELERY_TASK_RETRIES_TOTAL").labels(task_name=task_name).inc()


def record_task_queue_wait(task_name: str, queue: str, duration_s: float) -> None:
    _facade_metric("TASK_QUEUE_WAIT_SECONDS").labels(task_name=task_name, queue=queue).observe(max(0.0, duration_s))


def record_pipeline_phase_duration(phase: str, component: str, mode: str, status: str, duration_s: float) -> None:
    _facade_metric("PIPELINE_PHASE_DURATION_SECONDS").labels(
        phase=phase,
        component=component,
        mode=mode,
        status=status,
    ).observe(max(0.0, duration_s))


def record_lineage_recompute(updated_count: int, merge_count: int) -> None:
    _facade_metric("LINEAGE_RECOMPUTE_RUNS_TOTAL").inc()
    if updated_count > 0:
        _facade_metric("LINEAGE_CATALOG_UPDATES_TOTAL").inc(updated_count)
    if merge_count > 0:
        _facade_metric("LINEAGE_COMPONENT_MERGES_TOTAL").inc(merge_count)

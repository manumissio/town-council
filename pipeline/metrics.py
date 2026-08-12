from __future__ import annotations

import logging
import os
import time
from typing import Final

from celery import signals
from prometheus_client import REGISTRY, start_http_server

from pipeline import metrics_celery_signals, metrics_provider_recorders, profiling
from pipeline.metrics_definitions import *  # noqa: F403 - compatibility facade for metric objects
from pipeline.metrics_profile_events import (
    TaskProfileContext,
    component_for_queue,
    write_task_profile_event,
    write_task_start_profile_event,
)
from pipeline.metrics_provider_keys import provider_base_labels_key, provider_labels_key
from pipeline.metrics_redis_backend import RedisProviderMetricsCollector
from pipeline.metrics_task_recorders import (
    record_lineage_recompute as _record_lineage_recompute,
    record_pipeline_phase_duration,
    record_task_duration,
    record_task_failure,
    record_task_queue_wait,
    record_task_retry,
)


logger = logging.getLogger(__name__)

WORKER_METRICS_PORT_ENV: Final = "TC_WORKER_METRICS_PORT"
METRICS_SERVER_ERRORS: Final = (OSError, ValueError)

_TASK_START: dict[str, float] = {}
_TASK_CONTEXT: dict[str, TaskProfileContext] = {}


def _provider_labels_key(provider: str, operation: str, model: str, outcome: str) -> str:
    return provider_labels_key(provider, operation, model, outcome)


def _provider_base_labels_key(provider: str, operation: str, model: str) -> str:
    return provider_base_labels_key(provider, operation, model)


try:
    REGISTRY.register(RedisProviderMetricsCollector())
except ValueError:
    # Repeated imports in tests should reuse the existing collector registration.
    pass


def record_provider_request(provider: str, operation: str, model: str, outcome: str, duration_ms: float) -> None:
    metrics_provider_recorders.record_provider_request(
        provider,
        operation,
        model,
        outcome,
        duration_ms,
    )


def record_provider_ttft(provider: str, operation: str, model: str, outcome: str, ttft_ms: float) -> None:
    metrics_provider_recorders.record_provider_ttft(
        provider,
        operation,
        model,
        outcome,
        ttft_ms,
    )


def record_provider_tokens_per_sec(
    provider: str,
    operation: str,
    model: str,
    outcome: str,
    tokens_per_sec: float,
) -> None:
    metrics_provider_recorders.record_provider_tokens_per_sec(
        provider,
        operation,
        model,
        outcome,
        tokens_per_sec,
    )


def record_provider_token_counts(
    provider: str,
    operation: str,
    model: str,
    outcome: str,
    prompt_tokens: int,
    completion_tokens: int,
) -> None:
    metrics_provider_recorders.record_provider_token_counts(
        provider,
        operation,
        model,
        outcome,
        prompt_tokens,
        completion_tokens,
    )


def record_provider_timeout(provider: str, operation: str, model: str) -> None:
    metrics_provider_recorders.record_provider_timeout(provider, operation, model)


def record_provider_retry(provider: str, operation: str, model: str) -> None:
    metrics_provider_recorders.record_provider_retry(provider, operation, model)


def record_lineage_recompute(updated_count: int, merge_count: int) -> None:
    _record_lineage_recompute(updated_count, merge_count)


@signals.worker_ready.connect
def _start_metrics_server(**_kwargs: object) -> None:
    port = os.getenv(WORKER_METRICS_PORT_ENV)
    if not port:
        return
    try:
        start_http_server(int(port))
    except METRICS_SERVER_ERRORS as error:
        logger.warning("metrics.worker_exporter_unavailable port=%s error_class=%s", port, type(error).__name__)


@signals.before_task_publish.connect
def _before_task_publish(
    sender: object = None,
    body: object = None,
    headers: dict[str, object] | None = None,
    routing_key: object = None,
    **_kwargs: object,
) -> None:
    metrics_celery_signals.before_task_publish(
        headers,
        sender=sender,
        body=body,
        routing_key=routing_key,
        profiling_module=profiling,
        time_module=time,
    )


@signals.after_task_publish.connect
def _after_task_publish(
    sender: object = None,
    body: object = None,
    headers: dict[str, object] | None = None,
    routing_key: object = None,
    **_kwargs: object,
) -> None:
    metrics_celery_signals.after_task_publish(
        headers,
        sender=sender,
        body=body,
        routing_key=routing_key,
        profiling_module=profiling,
    )


@signals.task_prerun.connect
def _task_prerun(task_id: object = None, task: object = None, **_kwargs: object) -> None:
    context = metrics_celery_signals.task_prerun(
        task_id=task_id,
        task=task,
        task_start=_TASK_START,
        task_context=_TASK_CONTEXT,
        time_module=time,
        record_queue_wait=record_task_queue_wait,
        profiling_module=profiling,
    )
    if context is not None:
        write_task_start_profile_event(context, profiling_module=profiling)


@signals.task_postrun.connect
def _task_postrun(task_id: object = None, task: object = None, state: object = None, **_kwargs: object) -> None:
    metrics_celery_signals.task_postrun(
        task_id=task_id,
        task=task,
        state=state,
        task_start=_TASK_START,
        task_context=_TASK_CONTEXT,
        time_module=time,
        profiling_module=profiling,
        record_task_duration=record_task_duration,
        record_phase_duration=record_pipeline_phase_duration,
        write_profile_event=_write_task_profile_event,
    )


@signals.task_failure.connect
def _task_failure(
    task_id: object = None, exception: BaseException | None = None, sender: object = None, **_kwargs: object
) -> None:
    metrics_celery_signals.task_failure(
        task_id=task_id,
        exception=exception,
        sender=sender,
        task_start=_TASK_START,
        task_context=_TASK_CONTEXT,
        time_module=time,
        profiling_module=profiling,
        record_task_failure=record_task_failure,
        record_task_duration=record_task_duration,
        record_phase_duration=record_pipeline_phase_duration,
        write_profile_event=_write_task_profile_event,
    )


@signals.task_retry.connect
def _task_retry(request: object = None, **_kwargs: object) -> None:
    metrics_celery_signals.task_retry(request, record_task_retry=record_task_retry)


def _write_task_profile_event(
    context: TaskProfileContext,
    task_name: str,
    status: str,
    duration_s: float,
    exception_type: str | None = None,
) -> None:
    write_task_profile_event(
        context,
        task_name=task_name,
        status=status,
        duration_s=duration_s,
        profiling_module=profiling,
        exception_type=exception_type,
    )


_component_for_queue = component_for_queue

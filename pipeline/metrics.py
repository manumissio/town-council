from __future__ import annotations

import logging
import os
import time
from typing import Final

from celery import signals
from prometheus_client import REGISTRY, start_http_server

from pipeline import metrics_celery_signals, metrics_provider_recorders, profiling
from pipeline.metrics_definitions import *  # noqa: F403 - compatibility facade for metric objects
from pipeline.metrics_profile_events import TaskProfileContext, component_for_queue, write_task_profile_event
from pipeline.metrics_provider_collector import RedisProviderMetricsCollector as _RedisProviderMetricsCollector
from pipeline.metrics_provider_keys import provider_base_labels_key, provider_labels_key
from pipeline.metrics_task_recorders import (
    record_lineage_recompute as _record_lineage_recompute,
    record_pipeline_phase_duration,
    record_task_duration,
    record_task_failure,
    record_task_queue_wait,
    record_task_retry,
)


logger = logging.getLogger(__name__)
try:
    import redis  # type: ignore[import-untyped]
except ImportError:
    redis = None  # type: ignore[assignment]
    REDIS_OPERATION_ERRORS: Final[tuple[type[BaseException], ...]] = ()
else:
    REDIS_OPERATION_ERRORS = (redis.RedisError,)

REDIS_HOST_ENV: Final = "REDIS_HOST"
REDIS_PORT_ENV: Final = "REDIS_PORT"
REDIS_PASSWORD_ENV: Final = "REDIS_PASSWORD"
WORKER_METRICS_PORT_ENV: Final = "TC_WORKER_METRICS_PORT"
DEFAULT_REDIS_HOST: Final = "redis"
DEFAULT_REDIS_PORT: Final = "6379"
REDIS_DB: Final = 0
REDIS_WRITE_ERRORS: Final = REDIS_OPERATION_ERRORS + (OSError, RuntimeError, TimeoutError, TypeError, ValueError)
METRICS_SERVER_ERRORS: Final = (OSError, ValueError)

_TASK_START: dict[str, float] = {}
_TASK_CONTEXT: dict[str, TaskProfileContext] = {}
_REDIS_CLIENT = None
_REDIS_INIT = False
_REDIS_WARNED = False
_REDIS_BACKEND_UP = 0.0

def _provider_labels_key(provider: str, operation: str, model: str, outcome: str) -> str:
    return provider_labels_key(provider, operation, model, outcome)

def _provider_base_labels_key(provider: str, operation: str, model: str) -> str:
    return provider_base_labels_key(provider, operation, model)

def _redis_client() -> object | None:
    global _REDIS_BACKEND_UP, _REDIS_CLIENT, _REDIS_INIT, _REDIS_WARNED
    if _REDIS_INIT:
        return _REDIS_CLIENT
    _REDIS_INIT = True

    if redis is None:
        if not _REDIS_WARNED:
            logger.warning("metrics.redis_unavailable redis module unavailable; provider metrics backend degraded")
            _REDIS_WARNED = True
        _REDIS_BACKEND_UP = 0.0
        return None

    try:
        _REDIS_CLIENT = redis.Redis(
            host=os.getenv(REDIS_HOST_ENV, DEFAULT_REDIS_HOST),
            port=int(os.getenv(REDIS_PORT_ENV, DEFAULT_REDIS_PORT)),
            password=os.getenv(REDIS_PASSWORD_ENV, "") or None,
            db=REDIS_DB,
            decode_responses=True,
        )
        _REDIS_CLIENT.ping()
        _REDIS_BACKEND_UP = 1.0
        return _REDIS_CLIENT
    except REDIS_WRITE_ERRORS as error:
        if not _REDIS_WARNED:
            logger.warning(
                "metrics.redis_backend_unavailable falling back to local metrics only error=%s",
                error,
            )
            _REDIS_WARNED = True
        _REDIS_BACKEND_UP = 0.0
        _REDIS_CLIENT = None
        return None

def _redis_incr(key: str, amount: int = 1) -> None:
    global _REDIS_BACKEND_UP
    client = _redis_client()
    if client is None:
        return
    try:
        client.incrby(key, int(amount))
    except REDIS_WRITE_ERRORS:
        _REDIS_BACKEND_UP = 0.0

def _redis_hincrby(key: str, field: str, amount: int = 1) -> None:
    global _REDIS_BACKEND_UP
    client = _redis_client()
    if client is None:
        return
    try:
        client.hincrby(key, field, int(amount))
    except REDIS_WRITE_ERRORS:
        _REDIS_BACKEND_UP = 0.0


def _redis_hincrbyfloat(key: str, field: str, amount: float) -> None:
    global _REDIS_BACKEND_UP
    client = _redis_client()
    if client is None:
        return
    try:
        client.hincrbyfloat(key, field, float(amount))
    except REDIS_WRITE_ERRORS:
        _REDIS_BACKEND_UP = 0.0


class RedisProviderMetricsCollector(_RedisProviderMetricsCollector):
    def __init__(self) -> None:
        super().__init__(_redis_client, _get_redis_backend_up, _set_redis_backend_up, read_errors=REDIS_WRITE_ERRORS)


def _get_redis_backend_up() -> float:
    return float(_REDIS_BACKEND_UP)

def _set_redis_backend_up(value: float) -> None:
    global _REDIS_BACKEND_UP
    _REDIS_BACKEND_UP = float(value)


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
        redis_incr=_redis_incr,
    )


def record_provider_ttft(provider: str, operation: str, model: str, outcome: str, ttft_ms: float) -> None:
    metrics_provider_recorders.record_provider_ttft(
        provider,
        operation,
        model,
        outcome,
        ttft_ms,
        redis_hincrby=_redis_hincrby,
        redis_hincrbyfloat=_redis_hincrbyfloat,
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
        redis_hincrby=_redis_hincrby,
        redis_hincrbyfloat=_redis_hincrbyfloat,
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
        redis_incr=_redis_incr,
    )


def record_provider_timeout(provider: str, operation: str, model: str) -> None:
    metrics_provider_recorders.record_provider_timeout(provider, operation, model, redis_incr=_redis_incr)


def record_provider_retry(provider: str, operation: str, model: str) -> None:
    metrics_provider_recorders.record_provider_retry(provider, operation, model, redis_incr=_redis_incr)


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
def _before_task_publish(headers: dict[str, object] | None = None, **_kwargs: object) -> None:
    metrics_celery_signals.before_task_publish(headers, profiling_module=profiling, time_module=time)


@signals.task_prerun.connect
def _task_prerun(task_id: object = None, task: object = None, **_kwargs: object) -> None:
    metrics_celery_signals.task_prerun(
        task_id=task_id,
        task=task,
        task_start=_TASK_START,
        task_context=_TASK_CONTEXT,
        time_module=time,
        record_queue_wait=record_task_queue_wait,
    )


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
def _task_failure(task_id: object = None, exception: BaseException | None = None, sender: object = None, **_kwargs: object) -> None:
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

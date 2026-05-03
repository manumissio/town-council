from __future__ import annotations

from collections.abc import Callable, MutableMapping
from types import ModuleType

from pipeline.metrics_profile_events import TaskProfileContext, catalog_id_from_request, component_for_queue

RecordQueueWait = Callable[[str, str, float], None]
RecordTaskDuration = Callable[[str, str, float], None]
RecordTaskFailure = Callable[[str, str], None]
RecordTaskRetry = Callable[[str], None]
RecordPhaseDuration = Callable[[str, str, str, str, float], None]
WriteProfileEvent = Callable[[TaskProfileContext, str, str, float, str | None], None]


def before_task_publish(
    headers: MutableMapping[str, object] | None,
    *,
    profiling_module: ModuleType,
    time_module: ModuleType,
) -> None:
    if headers is None:
        return
    if headers.get("tc_queued_at") is None:
        headers["tc_queued_at"] = time_module.time()
    run_id = profiling_module.current_run_id()
    if not run_id:
        return
    headers.setdefault("tc_profile_run_id", run_id)
    headers.setdefault("tc_profile_mode", profiling_module.current_mode())
    artifact_dir = profiling_module.os.getenv(profiling_module.PROFILE_ARTIFACT_DIR_ENV, "")
    if artifact_dir:
        headers.setdefault("tc_profile_artifact_dir", artifact_dir)
    headers.setdefault("tc_profile_baseline_valid", "1" if profiling_module.baseline_valid() else "0")


def task_prerun(
    *,
    task_id: object,
    task: object,
    task_start: MutableMapping[str, float],
    task_context: MutableMapping[str, TaskProfileContext],
    time_module: ModuleType,
    record_queue_wait: RecordQueueWait,
) -> None:
    if not task_id or task is None:
        return
    task_id_value = str(task_id)
    task_start[task_id_value] = time_module.perf_counter()
    request = getattr(task, "request", None)
    headers = getattr(request, "headers", None) or {}
    delivery = getattr(request, "delivery_info", None) or {}
    task_name = str(getattr(task, "name", "unknown"))
    queue = str(delivery.get("routing_key") or delivery.get("queue") or "celery")
    queue_wait_s = _record_queue_wait_from_headers(headers, task_name, queue, time_module, record_queue_wait)
    task_context[task_id_value] = TaskProfileContext(
        task_name=task_name,
        queue=queue,
        queue_wait_s=queue_wait_s,
        queued_at=headers.get("tc_queued_at"),
        run_id=_optional_str(headers.get("tc_profile_run_id")),
        mode=_optional_str(headers.get("tc_profile_mode")),
        artifact_dir=_optional_str(headers.get("tc_profile_artifact_dir")),
        baseline_valid=_optional_str(headers.get("tc_profile_baseline_valid")),
        catalog_id=catalog_id_from_request(request),
    )


def task_postrun(
    *,
    task_id: object,
    task: object,
    state: object,
    task_start: MutableMapping[str, float],
    task_context: MutableMapping[str, TaskProfileContext],
    time_module: ModuleType,
    profiling_module: ModuleType,
    record_task_duration: RecordTaskDuration,
    record_phase_duration: RecordPhaseDuration,
    write_profile_event: WriteProfileEvent,
) -> None:
    if not task_id or task is None:
        return
    task_id_value = str(task_id)
    start = task_start.pop(task_id_value, None)
    context = task_context.pop(task_id_value, None)
    if start is None:
        return
    status = "success" if str(state or "").lower() in ("success", "succeeded") else "unknown"
    task_name = str(getattr(task, "name", "unknown"))
    duration_s = time_module.perf_counter() - start
    _record_task_span(
        context,
        task_name=task_name,
        status=status,
        duration_s=duration_s,
        profiling_module=profiling_module,
        record_task_duration=record_task_duration,
        record_phase_duration=record_phase_duration,
        write_profile_event=write_profile_event,
    )


def task_failure(
    *,
    task_id: object,
    exception: BaseException | None,
    sender: object,
    task_start: MutableMapping[str, float],
    task_context: MutableMapping[str, TaskProfileContext],
    time_module: ModuleType,
    profiling_module: ModuleType,
    record_task_failure: RecordTaskFailure,
    record_task_duration: RecordTaskDuration,
    record_phase_duration: RecordPhaseDuration,
    write_profile_event: WriteProfileEvent,
) -> None:
    task_name = str(getattr(sender, "name", "unknown"))
    exception_type = type(exception).__name__ if exception is not None else "Exception"
    record_task_failure(task_name, exception_type)
    if not task_id:
        return
    task_id_value = str(task_id)
    start = task_start.pop(task_id_value, None)
    context = task_context.pop(task_id_value, None)
    if start is None:
        return
    _record_task_span(
        context,
        task_name=task_name,
        status="failure",
        duration_s=time_module.perf_counter() - start,
        profiling_module=profiling_module,
        record_task_duration=record_task_duration,
        record_phase_duration=record_phase_duration,
        write_profile_event=write_profile_event,
        exception_type=exception_type,
    )


def task_retry(request: object, *, record_task_retry: RecordTaskRetry) -> None:
    task_name = getattr(getattr(request, "task", None), "name", None) or getattr(request, "task_name", None) or "unknown"
    record_task_retry(str(task_name))


def _record_queue_wait_from_headers(
    headers: object,
    task_name: str,
    queue: str,
    time_module: ModuleType,
    record_queue_wait: RecordQueueWait,
) -> float | None:
    try:
        queued_at = float(headers.get("tc_queued_at"))  # type: ignore[attr-defined]
    except (AttributeError, TypeError, ValueError):
        return None
    queue_wait_s = max(0.0, time_module.time() - queued_at)
    record_queue_wait(task_name, queue, queue_wait_s)
    return queue_wait_s


def _record_task_span(
    context: TaskProfileContext | None,
    *,
    task_name: str,
    status: str,
    duration_s: float,
    profiling_module: ModuleType,
    record_task_duration: RecordTaskDuration,
    record_phase_duration: RecordPhaseDuration,
    write_profile_event: WriteProfileEvent,
    exception_type: str | None = None,
) -> None:
    queue = context.queue if context is not None else None
    mode = str((context.mode if context is not None else None) or "triage")
    record_task_duration(task_name, status, duration_s)
    record_phase_duration(
        profiling_module.phase_from_task_name(task_name),
        component_for_queue(queue),
        mode,
        status,
        duration_s,
    )
    if context is not None:
        write_profile_event(context, task_name, status, duration_s, exception_type)


def _optional_str(raw_value: object) -> str | None:
    if raw_value is None:
        return None
    return str(raw_value)

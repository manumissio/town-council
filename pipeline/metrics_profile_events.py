from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Literal


DispatchBoundary = Literal["before", "after"]


@dataclass(slots=True)
class TaskProfileContext:
    task_name: str
    task_id: str
    execution_id: str
    retry_ordinal: int | None
    redelivered: bool | None
    queue: str
    queue_wait_s: float | None
    queued_at: object
    run_id: str | None
    mode: str | None
    artifact_dir: str | None
    baseline_valid: str | None
    catalog_id: int | None
    observer_at_start: float


@dataclass(frozen=True, slots=True)
class DispatchProfileContext:
    run_id: str
    mode: str
    artifact_dir: Path
    baseline_valid: bool


def catalog_id_from_request(request: object) -> int | None:
    args = getattr(request, "args", None) or ()
    if not args:
        return None
    try:
        return int(args[0])
    except (TypeError, ValueError):
        return None


def catalog_id_from_publish_body(body: object) -> int | None:
    task_args: object = None
    if isinstance(body, Mapping):
        task_args = body.get("args")
    elif isinstance(body, Sequence) and not isinstance(body, str | bytes) and body:
        task_args = body[0]
    if not isinstance(task_args, Sequence) or isinstance(task_args, str | bytes) or not task_args:
        return None
    catalog_id = task_args[0]
    if not isinstance(catalog_id, int) or isinstance(catalog_id, bool):
        return None
    return catalog_id


def _publish_field(
    headers: Mapping[str, object] | None,
    body: object,
    field_name: str,
) -> object:
    if headers is not None and headers.get(field_name) is not None:
        return headers[field_name]
    if isinstance(body, Mapping):
        return body.get(field_name)
    return None


def append_task_dispatch_event(
    *,
    boundary: DispatchBoundary,
    sender: object,
    body: object,
    headers: Mapping[str, object] | None,
    routing_key: object,
    profiling_module: ModuleType,
) -> None:
    profile_context = _dispatch_profile_context(headers, body)
    if profile_context is None:
        return
    task_id = str(_publish_field(headers, body, "id") or "").strip()
    if not task_id:
        return
    task_name = str(sender or _publish_field(headers, body, "task") or "unknown")
    retries = _publish_field(headers, body, "retries")
    retry_ordinal = retries if isinstance(retries, int) and not isinstance(retries, bool) and retries >= 0 else None
    with profiling_module.profile_observer():
        profiling_module.append_jsonl(
            profile_context.artifact_dir / "spans.jsonl",
            {
                "run_id": profile_context.run_id,
                "mode": profile_context.mode,
                "baseline_valid": profile_context.baseline_valid,
                "timestamp": profiling_module.utc_now_iso(),
                "event_type": "task_dispatch",
                "boundary": boundary,
                "task_id": task_id,
                "task_name": task_name,
                "queue": str(routing_key or "celery"),
                "queued_at": _publish_field(headers, body, "tc_queued_at"),
                "retry_ordinal": retry_ordinal,
                "catalog_id": catalog_id_from_publish_body(body),
            },
        )


def _dispatch_profile_context(
    headers: Mapping[str, object] | None,
    body: object,
) -> DispatchProfileContext | None:
    run_id = str(_publish_field(headers, body, "tc_profile_run_id") or "").strip()
    artifact_dir = str(
        _publish_field(headers, body, "tc_profile_artifact_dir") or ""
    ).strip()
    if not run_id or not artifact_dir:
        return None
    mode = str(_publish_field(headers, body, "tc_profile_mode") or "triage")
    baseline_value = str(
        _publish_field(headers, body, "tc_profile_baseline_valid") or "0"
    ).lower()
    return DispatchProfileContext(
        run_id=run_id,
        mode=mode,
        artifact_dir=Path(artifact_dir),
        baseline_valid=baseline_value in {"1", "true", "yes"},
    )


def component_for_queue(queue: object) -> str:
    value = str(queue or "")
    if value == "enrichment":
        return "enrichment-worker"
    if value == "semantic":
        return "semantic-worker"
    return "worker"


def write_task_profile_event(
    context: TaskProfileContext,
    *,
    task_name: str,
    status: str,
    duration_s: float,
    profiling_module: ModuleType,
    exception_type: str | None = None,
) -> None:
    profile_event = _task_profile_event(context, task_name, profiling_module)
    if profile_event is None:
        return
    profile_event.update(
        {
            "event_type": "task_span",
            "duration_s": round(float(duration_s), 6),
            "outcome": status,
            "metadata": {"exception_type": exception_type} if exception_type else None,
        }
    )
    _append_task_profile_event(context, profile_event, profiling_module)


def write_task_start_profile_event(
    context: TaskProfileContext,
    *,
    profiling_module: ModuleType,
) -> None:
    with profiling_module.profile_observer():
        profile_event = _task_profile_event(context, context.task_name, profiling_module)
        if profile_event is None:
            return
        profile_event["event_type"] = "task_start"
        _append_task_profile_event(context, profile_event, profiling_module)


def _task_profile_event(
    context: TaskProfileContext,
    task_name: str,
    profiling_module: ModuleType,
) -> dict[str, object] | None:
    if not str(context.run_id or "").strip() or not str(context.artifact_dir or "").strip():
        return None
    return {
        "phase": profiling_module.phase_from_task_name(task_name),
        "component": component_for_queue(context.queue),
        "catalog_id": context.catalog_id,
        "task_name": task_name,
        "task_id": context.task_id,
        "execution_id": context.execution_id,
        "retry_ordinal": context.retry_ordinal,
        "redelivered": context.redelivered,
        "queue": context.queue,
        "queued_at": context.queued_at,
        "queue_wait_s": context.queue_wait_s,
    }


def _append_task_profile_event(
    context: TaskProfileContext,
    profile_event: dict[str, object],
    profiling_module: ModuleType,
) -> None:
    artifact_dir = Path(str(context.artifact_dir))
    profiling_module.append_jsonl(
        artifact_dir / "spans.jsonl",
        {
            "run_id": str(context.run_id),
            "mode": str(context.mode or "triage"),
            "baseline_valid": str(context.baseline_valid or "0").lower() in {"1", "true", "yes"},
            "timestamp": profiling_module.utc_now_iso(),
            **profile_event,
        },
    )

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import ModuleType


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


def catalog_id_from_request(request: object) -> int | None:
    args = getattr(request, "args", None) or ()
    if not args:
        return None
    try:
        return int(args[0])
    except (TypeError, ValueError):
        return None


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

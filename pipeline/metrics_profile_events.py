from __future__ import annotations

import os
from dataclasses import dataclass
from types import ModuleType


@dataclass(slots=True)
class TaskProfileContext:
    task_name: str
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
    run_id = str(context.run_id or "").strip()
    artifact_dir = str(context.artifact_dir or "").strip()
    if not run_id or not artifact_dir:
        return
    previous = {
        profiling_module.PROFILE_RUN_ID_ENV: os.getenv(profiling_module.PROFILE_RUN_ID_ENV),
        profiling_module.PROFILE_MODE_ENV: os.getenv(profiling_module.PROFILE_MODE_ENV),
        profiling_module.PROFILE_ARTIFACT_DIR_ENV: os.getenv(profiling_module.PROFILE_ARTIFACT_DIR_ENV),
        profiling_module.PROFILE_BASELINE_VALID_ENV: os.getenv(profiling_module.PROFILE_BASELINE_VALID_ENV),
    }
    try:
        os.environ[profiling_module.PROFILE_RUN_ID_ENV] = run_id
        os.environ[profiling_module.PROFILE_MODE_ENV] = str(context.mode or "triage")
        os.environ[profiling_module.PROFILE_ARTIFACT_DIR_ENV] = artifact_dir
        os.environ[profiling_module.PROFILE_BASELINE_VALID_ENV] = str(context.baseline_valid or "0")
        profiling_module.append_profile_event(
            {
                "event_type": "task_span",
                "phase": profiling_module.phase_from_task_name(task_name),
                "component": component_for_queue(context.queue),
                "catalog_id": context.catalog_id,
                "task_name": task_name,
                "queue": context.queue,
                "queued_at": context.queued_at,
                "queue_wait_s": context.queue_wait_s,
                "duration_s": round(float(duration_s), 6),
                "outcome": status,
                "metadata": {"exception_type": exception_type} if exception_type else None,
            }
        )
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

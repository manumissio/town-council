from __future__ import annotations

import sys
from typing import Any, Callable

from pipeline.task_runtime import logger


def get_celery_pool_from_argv(argv: list[str]) -> str | None:
    """
    Best-effort extraction of the Celery pool from argv.

    Why this exists:
    Celery's worker-ready sender is not a stable place to read pool details across
    versions, but argv is stable for our worker entrypoint.
    """
    if not argv:
        return None
    for index, arg in enumerate(argv):
        if arg.startswith("--pool="):
            return arg.split("=", 1)[1].strip() or None
        if arg == "--pool" and (index + 1) < len(argv):
            return (argv[index + 1] or "").strip() or None
    return None


def run_startup_purge_on_worker_ready(
    sender=None,
    *,
    backend: str | None,
    allow_multiprocess: bool,
    require_solo_pool: bool,
    guardrail_message_builder: Callable[..., str | None],
    startup_purge_callable: Callable[[], Any],
) -> None:
    """
    Keep worker startup policy in one place while leaving the signal binding in tasks.py.
    """
    try:
        normalized_backend = (backend or "inprocess").strip().lower()
        concurrency = getattr(sender, "concurrency", None)
        if concurrency is None and sender is not None:
            concurrency = getattr(getattr(sender, "app", None), "conf", {}).get("worker_concurrency")  # type: ignore[attr-defined]
        try:
            if concurrency is not None:
                concurrency = int(concurrency)
        except Exception:  # noqa: BLE001
            concurrency = None

        pool = get_celery_pool_from_argv(getattr(sender, "argv", None) or sys.argv)  # type: ignore[arg-type]
        guardrail_message = guardrail_message_builder(
            backend=normalized_backend,
            allow_multiprocess=allow_multiprocess,
            require_solo_pool=require_solo_pool,
            concurrency=concurrency,
            pool=pool,
        )
        if guardrail_message:
            logger.critical(guardrail_message)
            raise SystemExit(1)
    except SystemExit:
        raise
    except Exception as guardrail_error:  # noqa: BLE001
        # Startup should stay resilient in non-worker contexts, but we still log
        # guardrail failures so a bad environment never disappears silently.
        logger.warning("worker_ready.guardrail_check_failed error=%s", guardrail_error)

    result = startup_purge_callable()
    logger.info("startup_purge_result=%s", result)

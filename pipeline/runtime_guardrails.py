import os
from typing import SupportsInt


def _coerce_int(value: str | SupportsInt | None) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except Exception:
        return None


def local_ai_runtime_guardrail_message(
    *,
    backend: str,
    allow_multiprocess: bool,
    require_solo_pool: bool,
    concurrency: int | None,
    pool: str | None,
) -> str | None:
    normalized_backend = (backend or "inprocess").strip().lower() or "inprocess"
    normalized_pool = (pool or "").strip().lower() or None
    normalized_concurrency = _coerce_int(concurrency)

    if normalized_backend != "inprocess" or allow_multiprocess:
        return None
    if require_solo_pool and normalized_pool != "solo":
        return (
            "Unsafe worker pool for LocalAI: pool=%s. "
            "Run Celery with --pool=solo --concurrency=1, or set LOCAL_AI_BACKEND=http "
            "for a dedicated inference service."
        ) % (normalized_pool,)
    if isinstance(normalized_concurrency, int) and normalized_concurrency > 1:
        return (
            "Unsafe worker concurrency for LocalAI: concurrency=%s pool=%s. "
            "Run Celery with --concurrency=1 --pool=solo, or set LOCAL_AI_BACKEND=http "
            "for a dedicated inference service."
        ) % (normalized_concurrency, normalized_pool)
    return None


def local_ai_guardrail_inputs_from_env() -> tuple[int | None, str | None]:
    concurrency = None
    for key in ("WORKER_CONCURRENCY", "CELERYD_CONCURRENCY", "CELERY_WORKER_CONCURRENCY"):
        concurrency = _coerce_int(os.getenv(key))
        if concurrency is not None:
            break
    pool = None
    for key in ("WORKER_POOL", "CELERY_WORKER_POOL"):
        value = (os.getenv(key) or "").strip()
        if value:
            pool = value
            break
    return concurrency, pool

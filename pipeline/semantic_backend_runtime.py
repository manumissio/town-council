from __future__ import annotations

import os

from pipeline.semantic_backend_types import SemanticBackend

SEMANTIC_WORKER_CONCURRENCY_ENVS = ("UVICORN_WORKERS", "WEB_CONCURRENCY", "WORKER_CONCURRENCY", "CELERYD_CONCURRENCY")


def _looks_like_multiprocess_worker() -> bool:
    """
    Local embedding and FAISS index memory is process-local.
    We fail fast by default when a runtime looks multiprocess to avoid OOM surprises.
    """
    # Do not use process-name heuristics here: uvicorn --reload runs child processes
    # even with a single serving worker, which caused false-positive startup failures.
    # We gate on explicit worker concurrency envs instead.
    for env_name in SEMANTIC_WORKER_CONCURRENCY_ENVS:
        env_value = os.getenv(env_name)
        if not env_value:
            continue
        try:
            if int(env_value) > 1:
                return True
        except ValueError:
            continue
    return False


def get_semantic_backend() -> SemanticBackend:
    from pipeline import semantic_index

    backend_name = (semantic_index.SEMANTIC_BACKEND or "faiss").strip().lower()
    if backend_name == "pgvector":
        return semantic_index.PgvectorSemanticBackend()
    return semantic_index.FaissSemanticBackend()

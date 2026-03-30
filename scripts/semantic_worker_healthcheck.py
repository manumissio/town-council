#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

from scripts.worker_healthcheck import _probe_tcp, _socket_target_from_url


def main() -> int:
    failures: list[str] = []

    broker_failure = _probe_tcp(
        *_socket_target_from_url((os.getenv("CELERY_BROKER_URL") or "").strip()),
        label="redis broker",
    )
    if broker_failure:
        failures.append(broker_failure)

    database_failure = _probe_tcp(
        *_socket_target_from_url((os.getenv("DATABASE_URL") or "").strip()),
        label="postgres",
    )
    if database_failure:
        failures.append(database_failure)

    try:
        import torch  # noqa: F401
        import transformers  # noqa: F401
        import faiss  # noqa: F401
    except Exception as exc:
        failures.append(f"semantic runtime import probe failed: {exc}")

    try:
        import pipeline.semantic_tasks  # noqa: F401
        from pipeline.celery_app import app

        if "semantic.embed_catalog" not in app.tasks:
            failures.append("semantic task registration probe failed: semantic.embed_catalog is missing")
    except Exception as exc:
        failures.append(f"semantic task registration probe failed: {exc}")

    try:
        artifact_dir = Path(os.getenv("SEMANTIC_INDEX_DIR", "/app/data/semantic"))
        artifact_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=artifact_dir, prefix=".healthcheck-", delete=True):
            pass
    except Exception as exc:
        failures.append(f"semantic artifact directory probe failed: {exc}")

    if failures:
        for failure in failures:
            print(failure, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

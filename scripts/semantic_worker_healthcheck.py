#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import worker_health_probes

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

    failures = worker_health_probes.probe_broker_and_database(
        worker_health_probes.socket_target_from_url((os.getenv("CELERY_BROKER_URL") or "").strip()),
        worker_health_probes.socket_target_from_url((os.getenv("DATABASE_URL") or "").strip()),
    )

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

    return worker_health_probes.healthcheck_exit_code(failures)


if __name__ == "__main__":
    raise SystemExit(main())

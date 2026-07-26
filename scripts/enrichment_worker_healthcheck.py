#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
import sys
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
        import pipeline.enrichment_tasks  # noqa: F401
        from pipeline.celery_app import app

        if "enrichment.generate_topics" not in app.tasks:
            failures.append("enrichment task registration probe failed: enrichment.generate_topics is missing")
    except Exception as exc:
        failures.append(f"enrichment task registration probe failed: {exc}")

    for module_name in ("sklearn", "spacy", "pytextrank"):
        probe = subprocess.run(
            [sys.executable, "-c", f"import {module_name}"],
            check=False,
            capture_output=True,
            text=True,
        )
        if probe.returncode != 0:
            detail = (probe.stderr or probe.stdout).strip() or f"exit {probe.returncode}"
            failures.append(f"enrichment runtime import probe failed for {module_name}: {detail}")

    return worker_health_probes.healthcheck_exit_code(failures)


if __name__ == "__main__":
    raise SystemExit(main())

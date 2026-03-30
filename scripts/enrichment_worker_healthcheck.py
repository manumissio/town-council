#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
import sys

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

    if failures:
        for failure in failures:
            print(failure, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

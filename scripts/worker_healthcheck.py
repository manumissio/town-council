#!/usr/bin/env python3
from __future__ import annotations

import os
import socket
import sys
from urllib.parse import urlparse


def _socket_target_from_url(url: str) -> tuple[str | None, int | None]:
    parsed = urlparse(url)
    return parsed.hostname, parsed.port


def _socket_target_from_env(host_env: str, default_port: int) -> tuple[str | None, int | None]:
    host = (os.getenv(host_env) or "").strip()
    if not host:
        return None, None
    return host, default_port


def _probe_tcp(host: str | None, port: int | None, *, label: str) -> str | None:
    if not host or port is None:
        return f"{label} target is not configured"
    try:
        with socket.create_connection((host, port), timeout=2):
            return None
    except OSError as exc:
        return f"{label} probe failed: {exc}"


def main() -> int:
    failures: list[str] = []

    metrics_port = int((os.getenv("TC_WORKER_METRICS_PORT") or "8001").strip())
    metrics_failure = _probe_tcp("127.0.0.1", metrics_port, label="worker metrics")
    if metrics_failure:
        failures.append(metrics_failure)

    broker_target = _socket_target_from_url((os.getenv("CELERY_BROKER_URL") or "").strip())
    if broker_target == (None, None):
        broker_target = _socket_target_from_env("REDIS_HOST", 6379)
    broker_failure = _probe_tcp(*broker_target, label="redis broker")
    if broker_failure:
        failures.append(broker_failure)

    database_failure = _probe_tcp(
        *_socket_target_from_url((os.getenv("DATABASE_URL") or "").strip()),
        label="postgres",
    )
    if database_failure:
        failures.append(database_failure)

    if failures:
        for failure in failures:
            print(failure, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

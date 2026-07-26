from __future__ import annotations

import socket
import sys
from urllib.parse import urlparse


TCP_PROBE_TIMEOUT_SECONDS = 2
REDIS_BROKER_LABEL = "redis broker"
POSTGRES_LABEL = "postgres"

SocketTarget = tuple[str | None, int | None]


def socket_target_from_url(url: str) -> SocketTarget:
    parsed_url = urlparse(url)
    return parsed_url.hostname, parsed_url.port


def socket_target_from_host(host: str, default_port: int) -> SocketTarget:
    normalized_host = host.strip()
    if not normalized_host:
        return None, None
    return normalized_host, default_port


def probe_tcp(
    host: str | None,
    port: int | None,
    *,
    label: str,
) -> str | None:
    if not host or port is None:
        return f"{label} target is not configured"
    try:
        with socket.create_connection(
            (host, port),
            timeout=TCP_PROBE_TIMEOUT_SECONDS,
        ):
            return None
    except OSError as exc:
        return f"{label} probe failed: {exc}"


def probe_broker_and_database(
    broker_target: SocketTarget,
    database_target: SocketTarget,
) -> list[str]:
    failures: list[str] = []
    broker_failure = probe_tcp(*broker_target, label=REDIS_BROKER_LABEL)
    if broker_failure:
        failures.append(broker_failure)

    database_failure = probe_tcp(*database_target, label=POSTGRES_LABEL)
    if database_failure:
        failures.append(database_failure)
    return failures


def healthcheck_exit_code(failures: list[str]) -> int:
    for failure in failures:
        print(failure, file=sys.stderr)
    return 1 if failures else 0

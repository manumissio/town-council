from __future__ import annotations

import importlib
import socket
from contextlib import contextmanager
from pathlib import Path
from types import ModuleType
from typing import Iterator

import pytest


HEALTHCHECK_PATHS = (
    Path("scripts/worker_healthcheck.py"),
    Path("scripts/enrichment_worker_healthcheck.py"),
    Path("scripts/semantic_worker_healthcheck.py"),
)


def _health_probes() -> ModuleType:
    return importlib.import_module("scripts.worker_health_probes")


@contextmanager
def _listening_socket() -> Iterator[socket.socket]:
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(8)
    try:
        yield listener
    finally:
        listener.close()


def _closed_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as candidate:
        candidate.bind(("127.0.0.1", 0))
        return int(candidate.getsockname()[1])


def test_socket_target_from_url_parses_credentials_and_ipv6() -> None:
    health_probes = _health_probes()

    assert health_probes.socket_target_from_url("redis://:secret@redis:6379/0") == ("redis", 6379)
    assert health_probes.socket_target_from_url("postgresql://user:pass@[::1]:5432/db") == ("::1", 5432)


def test_socket_target_from_url_preserves_malformed_port_failure() -> None:
    health_probes = _health_probes()

    with pytest.raises(ValueError, match="Port could not be cast"):
        health_probes.socket_target_from_url("redis://redis:not-a-port/0")


def test_probe_tcp_reports_missing_and_refused_targets() -> None:
    health_probes = _health_probes()

    assert health_probes.probe_tcp(None, None, label="redis broker") == ("redis broker target is not configured")
    refusal = health_probes.probe_tcp(
        "127.0.0.1",
        _closed_local_port(),
        label="postgres",
    )
    assert refusal is not None
    assert refusal.startswith("postgres probe failed:")


def test_probe_tcp_accepts_reachable_loopback_target() -> None:
    health_probes = _health_probes()

    with _listening_socket() as listener:
        assert (
            health_probes.probe_tcp(
                "127.0.0.1",
                int(listener.getsockname()[1]),
                label="redis broker",
            )
            is None
        )


def test_probe_broker_and_database_collects_all_failures() -> None:
    health_probes = _health_probes()
    closed_port = _closed_local_port()

    failures = health_probes.probe_broker_and_database(
        ("127.0.0.1", closed_port),
        (None, None),
    )

    assert len(failures) == 2
    assert failures[0].startswith("redis broker probe failed:")
    assert failures[1] == "postgres target is not configured"


def test_healthcheck_exit_code_reports_each_failure_once(capsys) -> None:
    health_probes = _health_probes()

    assert health_probes.healthcheck_exit_code([]) == 0
    assert capsys.readouterr().err == ""

    failures = ["redis broker probe failed: refused", "postgres target is not configured"]
    assert health_probes.healthcheck_exit_code(failures) == 1
    assert capsys.readouterr().err.splitlines() == failures


def test_healthcheck_clis_import_one_probe_owner() -> None:
    for healthcheck_path in HEALTHCHECK_PATHS:
        source = healthcheck_path.read_text(encoding="utf-8")
        assert "import worker_health_probes" in source

    for role_healthcheck_path in HEALTHCHECK_PATHS[1:]:
        source = role_healthcheck_path.read_text(encoding="utf-8")
        assert "scripts.worker_healthcheck" not in source

    shared_source = Path("scripts/worker_health_probes.py").read_text(encoding="utf-8")
    assert "worker_healthcheck" not in shared_source
    assert "enrichment_worker_healthcheck" not in shared_source
    assert "semantic_worker_healthcheck" not in shared_source

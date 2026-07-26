from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from typing import ClassVar, Iterator


WORKER_HEALTHCHECK_PATH = Path("scripts/worker_healthcheck.py")
HEALTHCHECK_ENVIRONMENT_KEYS = (
    "TC_WORKER_METRICS_PORT",
    "CELERY_BROKER_URL",
    "REDIS_HOST",
    "DATABASE_URL",
    "LOCAL_AI_BACKEND",
    "LOCAL_AI_HTTP_API",
    "LOCAL_AI_HTTP_BASE_URL",
    "LOCAL_AI_HTTP_MODEL",
)


class _ProviderHandler(BaseHTTPRequestHandler):
    responses: ClassVar[dict[str, object]] = {}

    def do_GET(self) -> None:
        response_body = self.responses[self.path]
        payload = response_body if isinstance(response_body, bytes) else json.dumps(response_body).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args: object) -> None:
        return


@contextmanager
def _provider_server(responses: dict[str, object]) -> Iterator[str]:
    handler = type("ProviderHandler", (_ProviderHandler,), {"responses": responses})
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    server_thread = Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()
        server_thread.join()


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


def _healthcheck_environment(**overrides: str) -> dict[str, str]:
    healthcheck_environment = os.environ.copy()
    healthcheck_environment.pop("PYTHONPATH", None)
    for environment_key in HEALTHCHECK_ENVIRONMENT_KEYS:
        healthcheck_environment.pop(environment_key, None)
    healthcheck_environment.update(overrides)
    return healthcheck_environment


def _worker_network_environment(port: int) -> dict[str, str]:
    return {
        "TC_WORKER_METRICS_PORT": str(port),
        "CELERY_BROKER_URL": f"redis://127.0.0.1:{port}/0",
        "DATABASE_URL": (f"postgresql://user:pass@127.0.0.1:{port}/town_council_db"),
    }


def _run_worker_healthcheck(
    healthcheck_environment: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(WORKER_HEALTHCHECK_PATH)],
        check=False,
        capture_output=True,
        text=True,
        timeout=15,
        env=healthcheck_environment,
    )


def test_worker_healthcheck_runs_without_pythonpath_when_all_probes_pass() -> None:
    with _listening_socket() as listener:
        network_environment = _worker_network_environment(int(listener.getsockname()[1]))
        healthcheck = _run_worker_healthcheck(
            _healthcheck_environment(
                **network_environment,
                LOCAL_AI_BACKEND="disabled",
            )
        )

    assert healthcheck.returncode == 0
    assert healthcheck.stderr == ""


def test_worker_healthcheck_reports_all_network_failures() -> None:
    closed_port = _closed_local_port()
    network_environment = _worker_network_environment(closed_port)
    healthcheck = _run_worker_healthcheck(
        _healthcheck_environment(
            **network_environment,
            LOCAL_AI_BACKEND="disabled",
        )
    )

    assert healthcheck.returncode == 1
    assert "worker metrics probe failed:" in healthcheck.stderr
    assert "redis broker probe failed:" in healthcheck.stderr
    assert "postgres probe failed:" in healthcheck.stderr


def test_worker_healthcheck_retains_redis_host_fallback() -> None:
    healthcheck = _run_worker_healthcheck(
        _healthcheck_environment(
            TC_WORKER_METRICS_PORT=str(_closed_local_port()),
            REDIS_HOST="town-council-invalid.invalid",
            LOCAL_AI_BACKEND="disabled",
        )
    )

    assert healthcheck.returncode == 1
    assert "redis broker probe failed:" in healthcheck.stderr
    assert "redis broker target is not configured" not in healthcheck.stderr


def test_worker_healthcheck_preserves_invalid_metrics_port_failure() -> None:
    healthcheck = _run_worker_healthcheck(_healthcheck_environment(TC_WORKER_METRICS_PORT="not-a-port"))

    assert healthcheck.returncode != 0
    assert "ValueError: invalid literal" in healthcheck.stderr


def test_worker_healthcheck_reports_missing_ollama_model() -> None:
    with _listening_socket() as listener, _provider_server({"/api/tags": {"models": []}}) as base_url:
        network_environment = _worker_network_environment(int(listener.getsockname()[1]))
        healthcheck = _run_worker_healthcheck(
            _healthcheck_environment(
                **network_environment,
                LOCAL_AI_BACKEND="http",
                LOCAL_AI_HTTP_API="ollama",
                LOCAL_AI_HTTP_BASE_URL=base_url,
                LOCAL_AI_HTTP_MODEL="gemma-3-270m-custom",
            )
        )

    assert healthcheck.returncode == 1
    assert ("inference model probe failed: api=ollama model 'gemma-3-270m-custom' is missing") in healthcheck.stderr


def test_worker_healthcheck_accepts_openai_compatible_model() -> None:
    responses = {
        "/health": {},
        "/v1/models": {"data": [{"id": "mlx-community/test-model"}]},
    }
    with _listening_socket() as listener, _provider_server(responses) as base_url:
        network_environment = _worker_network_environment(int(listener.getsockname()[1]))
        healthcheck = _run_worker_healthcheck(
            _healthcheck_environment(
                **network_environment,
                LOCAL_AI_BACKEND="http",
                LOCAL_AI_HTTP_API="openai_compat",
                LOCAL_AI_HTTP_BASE_URL=base_url,
                LOCAL_AI_HTTP_MODEL="mlx-community/test-model",
            )
        )

    assert healthcheck.returncode == 0
    assert healthcheck.stderr == ""


def test_worker_healthcheck_reports_malformed_provider_payload() -> None:
    with _listening_socket() as listener, _provider_server({"/api/tags": b"not-json"}) as base_url:
        network_environment = _worker_network_environment(int(listener.getsockname()[1]))
        healthcheck = _run_worker_healthcheck(
            _healthcheck_environment(
                **network_environment,
                LOCAL_AI_BACKEND="http",
                LOCAL_AI_HTTP_API="ollama",
                LOCAL_AI_HTTP_BASE_URL=base_url,
                LOCAL_AI_HTTP_MODEL="gemma-3-270m-custom",
            )
        )

    assert healthcheck.returncode == 1
    assert "inference model probe failed:" in healthcheck.stderr
    assert "Expecting value" in healthcheck.stderr

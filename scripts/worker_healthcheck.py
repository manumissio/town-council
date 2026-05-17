#!/usr/bin/env python3
from __future__ import annotations

import os
import socket
import sys
import json
import urllib.error
import urllib.request
from urllib.parse import urlparse


OPENAI_COMPAT_HTTP_API = "openai_compat"
OLLAMA_TAGS_PATH = "/api/tags"
OPENAI_HEALTH_PATH = "/health"
OPENAI_MODELS_PATH = "/v1/models"


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


def _read_json_url(url: str, *, timeout_seconds: int) -> dict[str, object]:
    try:
        with urllib.request.urlopen(url, timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, TimeoutError, urllib.error.URLError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"{exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("response payload is not an object")
    return payload


def _ollama_model_names(base_url: str) -> list[str]:
    payload = _read_json_url(f"{base_url.rstrip('/')}{OLLAMA_TAGS_PATH}", timeout_seconds=5)
    models = payload.get("models") or []
    return [entry.get("name") for entry in models if isinstance(entry, dict) and isinstance(entry.get("name"), str)]


def _openai_compatible_model_names(base_url: str) -> list[str]:
    try:
        with urllib.request.urlopen(f"{base_url.rstrip('/')}{OPENAI_HEALTH_PATH}", timeout=5):
            pass
        payload = _read_json_url(f"{base_url.rstrip('/')}{OPENAI_MODELS_PATH}", timeout_seconds=5)
    except (OSError, TimeoutError, urllib.error.URLError, RuntimeError) as exc:
        raise RuntimeError(f"{exc}") from exc
    models = payload.get("data") or []
    return [entry.get("id") for entry in models if isinstance(entry, dict) and isinstance(entry.get("id"), str)]


def _probe_http_model(base_url: str, model_name: str, http_api: str) -> str | None:
    try:
        model_names = (
            _openai_compatible_model_names(base_url)
            if http_api == OPENAI_COMPAT_HTTP_API
            else _ollama_model_names(base_url)
        )
    except RuntimeError as exc:
        return f"inference model probe failed: api={http_api} base_url={base_url} error={exc}"
    acceptable_names = {model_name, f"{model_name}:latest"}
    if any(model_name_candidate in acceptable_names for model_name_candidate in model_names):
        return None
    return f"inference model probe failed: api={http_api} model '{model_name}' is missing"


def _infrastructure_failures() -> list[str]:
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
    return failures


def _inference_failure() -> str | None:
    if (os.getenv("LOCAL_AI_BACKEND") or "http").strip().lower() == "http":
        return _probe_http_model(
            os.getenv("LOCAL_AI_HTTP_BASE_URL", "http://inference:11434").strip(),
            (os.getenv("LOCAL_AI_HTTP_MODEL") or "gemma-3-270m-custom").strip() or "gemma-3-270m-custom",
            (os.getenv("LOCAL_AI_HTTP_API") or "ollama").strip().lower() or "ollama",
        )
    return None


def main() -> int:
    failures = _infrastructure_failures()
    inference_failure = _inference_failure()
    if inference_failure:
        failures.append(inference_failure)
    if failures:
        for failure in failures:
            print(failure, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

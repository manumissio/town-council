#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

import worker_health_probes


OPENAI_COMPAT_HTTP_API = "openai_compat"
OLLAMA_TAGS_PATH = "/api/tags"
OPENAI_HEALTH_PATH = "/health"
OPENAI_MODELS_PATH = "/v1/models"
HTTP_PROBE_TIMEOUT_SECONDS = 5
WORKER_METRICS_DEFAULT_PORT = 8001
REDIS_DEFAULT_PORT = 6379
DEFAULT_HTTP_BASE_URL = "http://inference:11434"
DEFAULT_HTTP_MODEL = "gemma-3-270m-custom"
DEFAULT_HTTP_API = "ollama"


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
    payload = _read_json_url(
        f"{base_url.rstrip('/')}{OLLAMA_TAGS_PATH}",
        timeout_seconds=HTTP_PROBE_TIMEOUT_SECONDS,
    )
    models = payload.get("models") or []
    return [entry.get("name") for entry in models if isinstance(entry, dict) and isinstance(entry.get("name"), str)]


def _openai_compatible_model_names(base_url: str) -> list[str]:
    try:
        with urllib.request.urlopen(
            f"{base_url.rstrip('/')}{OPENAI_HEALTH_PATH}",
            timeout=HTTP_PROBE_TIMEOUT_SECONDS,
        ):
            pass
        payload = _read_json_url(
            f"{base_url.rstrip('/')}{OPENAI_MODELS_PATH}",
            timeout_seconds=HTTP_PROBE_TIMEOUT_SECONDS,
        )
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
    metrics_port = int((os.getenv("TC_WORKER_METRICS_PORT") or str(WORKER_METRICS_DEFAULT_PORT)).strip())
    metrics_failure = worker_health_probes.probe_tcp(
        "127.0.0.1",
        metrics_port,
        label="worker metrics",
    )
    if metrics_failure:
        failures.append(metrics_failure)

    broker_target = worker_health_probes.socket_target_from_url((os.getenv("CELERY_BROKER_URL") or "").strip())
    if broker_target == (None, None):
        broker_target = worker_health_probes.socket_target_from_host(
            os.getenv("REDIS_HOST") or "",
            REDIS_DEFAULT_PORT,
        )
    database_target = worker_health_probes.socket_target_from_url((os.getenv("DATABASE_URL") or "").strip())
    failures.extend(
        worker_health_probes.probe_broker_and_database(
            broker_target,
            database_target,
        )
    )
    return failures


def _inference_failure() -> str | None:
    if (os.getenv("LOCAL_AI_BACKEND") or "http").strip().lower() == "http":
        return _probe_http_model(
            os.getenv("LOCAL_AI_HTTP_BASE_URL", DEFAULT_HTTP_BASE_URL).strip(),
            (os.getenv("LOCAL_AI_HTTP_MODEL") or DEFAULT_HTTP_MODEL).strip() or DEFAULT_HTTP_MODEL,
            (os.getenv("LOCAL_AI_HTTP_API") or DEFAULT_HTTP_API).strip().lower() or DEFAULT_HTTP_API,
        )
    return None


def main() -> int:
    failures = _infrastructure_failures()
    inference_failure = _inference_failure()
    if inference_failure:
        failures.append(inference_failure)
    return worker_health_probes.healthcheck_exit_code(failures)


if __name__ == "__main__":
    raise SystemExit(main())

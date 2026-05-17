#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any

import requests


DEFAULT_OUTPUT_DIR = "experiments/results/model_probes"
PROFILE_KEYS = (
    "LOCAL_AI_BACKEND",
    "LOCAL_AI_HTTP_API",
    "LOCAL_AI_HTTP_BASE_URL",
    "LOCAL_AI_HTTP_PROFILE",
    "LOCAL_AI_HTTP_MODEL",
    "WORKER_CONCURRENCY",
    "WORKER_POOL",
    "OLLAMA_NUM_PARALLEL",
)
REASONING_TAG_PATTERN = re.compile(r"<\s*(think|analysis)\b", re.IGNORECASE)
OPENAI_COMPAT_HTTP_API = "openai_compat"
HTTP_API_CHOICES = ("ollama", OPENAI_COMPAT_HTTP_API)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _docker_memory_limit_bytes() -> int | None:
    try:
        completed = subprocess.run(
            ["docker", "info", "--format", "{{json .MemTotal}}"],
            check=True,
            text=True,
            capture_output=True,
        )
    except Exception:
        return None
    try:
        return int(json.loads(completed.stdout.strip()))
    except Exception:
        return None


def _git_commit_sha() -> str | None:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            text=True,
            capture_output=True,
        )
    except Exception:
        return None
    value = completed.stdout.strip()
    return value or None


def _profile_snapshot() -> dict[str, str]:
    return {
        key: value
        for key in PROFILE_KEYS
        if (value := os.getenv(key)) not in (None, "")
    }


def _ollama_model_names(base_url: str, timeout_seconds: int) -> list[str]:
    response = requests.get(f"{base_url.rstrip('/')}/api/tags", timeout=timeout_seconds)
    response.raise_for_status()
    payload = response.json()
    models = payload.get("models") if isinstance(payload, dict) else []
    out = []
    for model in models or []:
        name = (model or {}).get("name")
        if isinstance(name, str) and name.strip():
            out.append(name.strip())
    return out


def _openai_compatible_model_names(base_url: str, timeout_seconds: int) -> list[str]:
    health_response = requests.get(f"{base_url.rstrip('/')}/health", timeout=timeout_seconds)
    health_response.raise_for_status()
    response = requests.get(f"{base_url.rstrip('/')}/v1/models", timeout=timeout_seconds)
    response.raise_for_status()
    payload = response.json()
    models = payload.get("data") if isinstance(payload, dict) else []
    out = []
    for model in models or []:
        name = (model or {}).get("id")
        if isinstance(name, str) and name.strip():
            out.append(name.strip())
    return out


def _list_models(base_url: str, timeout_seconds: int, http_api: str) -> list[str]:
    if http_api == OPENAI_COMPAT_HTTP_API:
        return _openai_compatible_model_names(base_url, timeout_seconds)
    return _ollama_model_names(base_url, timeout_seconds)


def _normalize_probe_text(text: str) -> str:
    cleaned = text.strip().strip("`").strip()
    cleaned = re.sub(r"[^\w]+$", "", cleaned)
    return cleaned.upper()


def _ollama_probe_payload(model: str, prompt: str, max_tokens: int) -> dict[str, object]:
    return {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "num_predict": int(max_tokens),
            "temperature": 0.0,
        },
    }


def _openai_compatible_probe_payload(model: str, prompt: str, max_tokens: int) -> dict[str, object]:
    return {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0,
        "max_tokens": int(max_tokens),
        "stream": False,
    }


def _probe_endpoint(base_url: str, http_api: str) -> str:
    if http_api == OPENAI_COMPAT_HTTP_API:
        return f"{base_url.rstrip('/')}/v1/chat/completions"
    return f"{base_url.rstrip('/')}/api/generate"


def _probe_payload(http_api: str, model: str, prompt: str, max_tokens: int) -> dict[str, object]:
    if http_api == OPENAI_COMPAT_HTTP_API:
        return _openai_compatible_probe_payload(model, prompt, max_tokens)
    return _ollama_probe_payload(model, prompt, max_tokens)


def _response_text(payload: object, http_api: str) -> str | None:
    if not isinstance(payload, dict):
        return None
    if http_api != OPENAI_COMPAT_HTTP_API:
        raw_response = payload.get("response")
        return raw_response if isinstance(raw_response, str) else None
    return _openai_compatible_response_text(payload)


def _openai_compatible_response_text(payload: dict[str, object]) -> str | None:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        return None
    message = first_choice.get("message")
    if not isinstance(message, dict):
        return None
    content = message.get("content")
    return content if isinstance(content, str) else None


def _probe_model_availability(attempt: dict[str, Any], *, base_url: str, http_api: str, model: str, timeout_seconds: int) -> bool:
    try:
        models = _list_models(base_url, timeout_seconds, http_api)
    except Exception as exc:
        attempt["reason"] = f"health_check_failed:{exc.__class__.__name__}"
        return False

    acceptable = {model, f"{model}:latest"}
    attempt["available"] = any(name in acceptable for name in models)
    if not attempt["available"]:
        attempt["reason"] = "model_missing"
        return False
    return True


def _post_probe_request(
    *,
    base_url: str,
    http_api: str,
    model: str,
    prompt: str,
    timeout_seconds: int,
    max_tokens: int,
) -> object | None:
    response = requests.post(
        _probe_endpoint(base_url, http_api),
        json=_probe_payload(http_api, model, prompt, max_tokens),
        timeout=timeout_seconds,
    )
    response.raise_for_status()
    return response.json()


def probe_candidate(
    *,
    base_url: str,
    http_api: str,
    model: str,
    prompt: str,
    timeout_seconds: int,
    max_tokens: int,
) -> dict[str, Any]:
    attempt: dict[str, Any] = {
        "candidate": model,
        "status": "fail",
        "reason": "unknown",
        "available": False,
        "response_preview": None,
    }
    if not _probe_model_availability(
        attempt,
        base_url=base_url,
        http_api=http_api,
        model=model,
        timeout_seconds=timeout_seconds,
    ):
        return attempt

    try:
        payload = _post_probe_request(
            base_url=base_url,
            http_api=http_api,
            model=model,
            prompt=prompt,
            timeout_seconds=timeout_seconds,
            max_tokens=max_tokens,
        )
    except requests.exceptions.Timeout:
        attempt["reason"] = "prompt_timeout"
        return attempt
    except Exception as exc:
        attempt["reason"] = f"prompt_failed:{exc.__class__.__name__}"
        return attempt

    raw_response = _response_text(payload, http_api)
    if not isinstance(raw_response, str) or not raw_response.strip():
        attempt["reason"] = "empty_or_invalid_response"
        return attempt

    attempt["response_preview"] = raw_response.strip()[:160]
    if REASONING_TAG_PATTERN.search(raw_response):
        attempt["reason"] = "reasoning_tag_detected"
        return attempt
    if _normalize_probe_text(raw_response) != "READY":
        attempt["reason"] = "probe_contract_mismatch"
        return attempt

    attempt["status"] = "pass"
    attempt["reason"] = "probe_passed"
    return attempt


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Probe local HTTP inference candidates before running larger experiments.")
    parser.add_argument("--candidate", action="append", default=None, help="Candidate model tag to probe in order. Repeatable.")
    parser.add_argument("--allow-e4b", action="store_true", help="Append gemma4:e4b after gemma4:e2b when no explicit candidates are provided.")
    parser.add_argument("--api-base-url", default=os.getenv("LOCAL_AI_HTTP_BASE_URL", "http://localhost:11434"))
    parser.add_argument("--http-api", choices=HTTP_API_CHOICES, default=os.getenv("LOCAL_AI_HTTP_API", "ollama"))
    parser.add_argument("--timeout-seconds", type=int, default=20)
    parser.add_argument("--max-tokens", type=int, default=8)
    parser.add_argument("--prompt", default="Reply with exactly READY.")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args(argv)


def _candidate_models(args: argparse.Namespace) -> list[str]:
    candidates = [candidate.strip() for candidate in (args.candidate or []) if candidate and candidate.strip()]
    if candidates:
        return candidates
    default_candidates = ["gemma4:e2b"]
    if args.allow_e4b:
        default_candidates.append("gemma4:e4b")
    return default_candidates


def _http_api_arg(args: argparse.Namespace) -> str:
    return str(args.http_api or "ollama").strip().lower() or "ollama"


def _probe_attempts(args: argparse.Namespace, candidates: list[str], http_api: str) -> list[dict[str, Any]]:
    return [
        probe_candidate(
            base_url=args.api_base_url,
            http_api=http_api,
            model=model,
            prompt=args.prompt,
            timeout_seconds=max(5, int(args.timeout_seconds)),
            max_tokens=max(1, int(args.max_tokens)),
        )
        for model in candidates
    ]


def _probe_result_payload(
    *,
    run_id: str,
    args: argparse.Namespace,
    attempts: list[dict[str, Any]],
    selected: str | None,
    http_api: str,
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "started_at": _utc_now_iso(),
        "commit_sha": _git_commit_sha(),
        "status": "pass" if selected else "fail",
        "selected_candidate": selected,
        "attempts": attempts,
        "api_base_url": args.api_base_url,
        "http_api": http_api,
        "docker_memory_limit_bytes": _docker_memory_limit_bytes(),
        "profile": _profile_snapshot(),
        "prompt_contract": "candidate must return exactly READY without reasoning tags",
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    candidates = _candidate_models(args)
    http_api = _http_api_arg(args)
    run_id = args.run_id or f"model_probe_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    output_root = Path(args.output_dir)
    run_dir = output_root / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    attempts = _probe_attempts(args, candidates, http_api)
    selected = next((attempt["candidate"] for attempt in attempts if attempt.get("status") == "pass"), None)
    payload = _probe_result_payload(run_id=run_id, args=args, attempts=attempts, selected=selected, http_api=http_api)
    (run_dir / "probe_result.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0 if selected else 1


if __name__ == "__main__":
    raise SystemExit(main())

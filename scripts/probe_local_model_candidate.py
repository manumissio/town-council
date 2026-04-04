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
    "LOCAL_AI_HTTP_PROFILE",
    "LOCAL_AI_HTTP_MODEL",
    "WORKER_CONCURRENCY",
    "WORKER_POOL",
    "OLLAMA_NUM_PARALLEL",
)
REASONING_TAG_PATTERN = re.compile(r"<\s*(think|analysis)\b", re.IGNORECASE)


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


def _list_models(base_url: str, timeout_seconds: int) -> list[str]:
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


def _normalize_probe_text(text: str) -> str:
    cleaned = text.strip().strip("`").strip()
    cleaned = re.sub(r"[^\w]+$", "", cleaned)
    return cleaned.upper()


def probe_candidate(*, base_url: str, model: str, prompt: str, timeout_seconds: int, max_tokens: int) -> dict[str, Any]:
    attempt: dict[str, Any] = {
        "candidate": model,
        "status": "fail",
        "reason": "unknown",
        "available": False,
        "response_preview": None,
    }
    try:
        models = _list_models(base_url, timeout_seconds)
    except Exception as exc:
        attempt["reason"] = f"health_check_failed:{exc.__class__.__name__}"
        return attempt

    acceptable = {model, f"{model}:latest"}
    attempt["available"] = any(name in acceptable for name in models)
    if not attempt["available"]:
        attempt["reason"] = "model_missing"
        return attempt

    try:
        response = requests.post(
            f"{base_url.rstrip('/')}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "num_predict": int(max_tokens),
                    "temperature": 0.0,
                },
            },
            timeout=timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
    except requests.exceptions.Timeout:
        attempt["reason"] = "prompt_timeout"
        return attempt
    except Exception as exc:
        attempt["reason"] = f"prompt_failed:{exc.__class__.__name__}"
        return attempt

    raw_response = payload.get("response") if isinstance(payload, dict) else None
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
    parser.add_argument("--timeout-seconds", type=int, default=20)
    parser.add_argument("--max-tokens", type=int, default=8)
    parser.add_argument("--prompt", default="Reply with exactly READY.")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    candidates = [candidate.strip() for candidate in (args.candidate or []) if candidate and candidate.strip()]
    if not candidates:
        candidates = ["gemma4:e2b"]
        if args.allow_e4b:
            candidates.append("gemma4:e4b")

    run_id = args.run_id or f"model_probe_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    output_root = Path(args.output_dir)
    run_dir = output_root / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    attempts = [
        probe_candidate(
            base_url=args.api_base_url,
            model=model,
            prompt=args.prompt,
            timeout_seconds=max(5, int(args.timeout_seconds)),
            max_tokens=max(1, int(args.max_tokens)),
        )
        for model in candidates
    ]
    selected = next((attempt["candidate"] for attempt in attempts if attempt.get("status") == "pass"), None)
    payload = {
        "run_id": run_id,
        "started_at": _utc_now_iso(),
        "commit_sha": _git_commit_sha(),
        "status": "pass" if selected else "fail",
        "selected_candidate": selected,
        "attempts": attempts,
        "api_base_url": args.api_base_url,
        "docker_memory_limit_bytes": _docker_memory_limit_bytes(),
        "profile": _profile_snapshot(),
        "prompt_contract": "candidate must return exactly READY without reasoning tags",
    }
    (run_dir / "probe_result.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0 if selected else 1


if __name__ == "__main__":
    raise SystemExit(main())

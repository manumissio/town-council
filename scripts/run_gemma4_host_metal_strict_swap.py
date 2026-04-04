#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen


DEFAULT_RESULTS_ROOT = "experiments/results"
DEFAULT_ENV_FILE = "env/profiles/gemma4_e2b_host_metal_strict.env"
DEFAULT_CATALOG_FILE = "experiments/ab_catalogs_v1.txt"
SUPPORT_SERVICES = ["postgres", "redis", "meilisearch", "semantic", "semantic-worker", "tika"]
APP_SERVICES = ["worker", "api", "pipeline"]


def _run(
    cmd: list[str],
    *,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
    capture: bool = False,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        text=True,
        check=True,
        capture_output=capture,
    )


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _git_sha(repo_root: str) -> str:
    return _run(["git", "rev-parse", "HEAD"], cwd=repo_root, capture=True).stdout.strip()


def _load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        key, value = line.split("=", 1)
        values[key] = value
    return values


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _compose_env(base_env: dict[str, str], *, model: str) -> dict[str, str]:
    env = os.environ.copy()
    env.update(base_env)
    env["LOCAL_AI_HTTP_MODEL"] = model
    return env


def _host_http_json(url: str, *, timeout_seconds: int = 5) -> Any:
    try:
        with urlopen(url, timeout=timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except URLError as exc:
        raise RuntimeError(f"host ollama request failed: {exc}") from exc


def _host_tags(base_url: str) -> dict[str, Any]:
    payload = _host_http_json(f"{base_url.rstrip('/')}/api/tags")
    if not isinstance(payload, dict):
        raise RuntimeError("host ollama tags payload was not a JSON object")
    return payload


def _assert_host_model_available(tags_payload: dict[str, Any], model_name: str) -> None:
    acceptable_names = {model_name, f"{model_name}:latest"}
    models = tags_payload.get("models") or []
    if any((entry or {}).get("name") in acceptable_names for entry in models):
        return
    raise RuntimeError(f"host ollama is missing model '{model_name}'")


def _host_ollama_version(ollama_binary: str) -> str:
    completed = _run([ollama_binary, "--version"], capture=True)
    return completed.stdout.strip() or completed.stderr.strip()


def _host_ollama_ps(ollama_binary: str, *, base_url: str) -> str:
    env = os.environ.copy()
    env["OLLAMA_HOST"] = base_url.replace("http://", "").replace("https://", "")
    completed = _run([ollama_binary, "ps"], env=env, capture=True)
    return completed.stdout.strip()


def _stop_inference(repo_root: str) -> None:
    _run(["docker", "compose", "stop", "inference"], cwd=repo_root)


def _inference_running_state(repo_root: str) -> dict[str, Any]:
    try:
        completed = _run(
            [
                "docker",
                "inspect",
                "town-council-inference-1",
                "--format",
                "{{json .State}}",
            ],
            cwd=repo_root,
            capture=True,
        )
    except subprocess.CalledProcessError:
        return {"exists": False, "running": False, "raw_state": None}
    raw = completed.stdout.strip()
    state = json.loads(raw) if raw else {}
    return {"exists": True, "running": bool(state.get("Running")), "raw_state": state}


def _assert_inference_stopped(repo_root: str) -> dict[str, Any]:
    snapshot = _inference_running_state(repo_root)
    if snapshot["running"]:
        raise RuntimeError("docker inference service is still running")
    return snapshot


def _compose_up_without_inference(repo_root: str, *, env_file: str, env: dict[str, str]) -> None:
    _run(
        ["docker", "compose", "--env-file", env_file, "up", "-d", *SUPPORT_SERVICES],
        cwd=repo_root,
        env=env,
    )
    _run(
        [
            "docker",
            "compose",
            "--env-file",
            env_file,
            "up",
            "-d",
            "--force-recreate",
            "--no-deps",
            *APP_SERVICES,
        ],
        cwd=repo_root,
        env=env,
    )


def _worker_env_snapshot(repo_root: str) -> dict[str, str]:
    cmd = [
        "docker",
        "compose",
        "exec",
        "-T",
        "worker",
        "python",
        "-c",
        (
            "import json, os; "
            "keys=['LOCAL_AI_BACKEND','LOCAL_AI_HTTP_BASE_URL','LOCAL_AI_HTTP_PROFILE','LOCAL_AI_HTTP_MODEL',"
            "'LOCAL_AI_HTTP_TIMEOUT_SECONDS','LOCAL_AI_HTTP_TIMEOUT_SEGMENT_SECONDS',"
            "'LOCAL_AI_HTTP_TIMEOUT_SUMMARY_SECONDS','LOCAL_AI_HTTP_TIMEOUT_TOPICS_SECONDS',"
            "'LOCAL_AI_HTTP_MAX_RETRIES','WORKER_CONCURRENCY','WORKER_POOL','OLLAMA_NUM_PARALLEL']; "
            "print(json.dumps({k: os.getenv(k, '') for k in keys}, sort_keys=True))"
        ),
    ]
    out = _run(cmd, cwd=repo_root, capture=True).stdout.strip()
    return json.loads(out)


def _assert_worker_base_url(worker_env: dict[str, str], expected_url: str) -> None:
    actual = (worker_env.get("LOCAL_AI_HTTP_BASE_URL") or "").strip()
    if actual != expected_url:
        raise RuntimeError(f"worker LOCAL_AI_HTTP_BASE_URL mismatch: expected {expected_url}, got {actual or '<empty>'}")


def _worker_healthcheck(repo_root: str, *, env: dict[str, str]) -> None:
    _run(
        ["docker", "compose", "exec", "-T", "worker", "python", "scripts/worker_healthcheck.py"],
        cwd=repo_root,
        env=env,
    )


def _probe(repo_root: str, *, model: str, run_id: str, api_base_url: str) -> Path:
    _run(
        [
            "python3",
            "scripts/probe_local_model_candidate.py",
            "--candidate",
            model,
            "--api-base-url",
            api_base_url,
            "--output-dir",
            "experiments/results/model_probes",
            "--run-id",
            run_id,
        ],
        cwd=repo_root,
    )
    return Path(repo_root) / "experiments" / "results" / "model_probes" / run_id / "probe_result.json"


def _run_ab(repo_root: str, *, arm: str, catalog_file: str, run_id: str, model: str, env: dict[str, str]) -> Path:
    _run(
        [
            "./scripts/run_ab_eval.sh",
            "--arm",
            arm,
            "--catalog-file",
            catalog_file,
            "--run-id",
            run_id,
            "--arm-model",
            model,
        ],
        cwd=repo_root,
        env=env,
    )
    _run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "-w",
            "/app",
            "worker",
            "python",
            "scripts/collect_ab_results.py",
            "--run-id",
            run_id,
        ],
        cwd=repo_root,
        env=env,
    )
    return Path(repo_root) / "experiments" / "results" / run_id


def _write_run_artifact(
    path: Path,
    *,
    label: str,
    model: str,
    commit_sha: str,
    worker_env: dict[str, str],
    host_base_url: str,
    host_version: str,
    inference_state: dict[str, Any],
    host_ps: str,
    run_dir: Path | None = None,
    probe_path: Path | None = None,
) -> None:
    payload: dict[str, Any] = {
        "label": label,
        "model": model,
        "commit_sha": commit_sha,
        "worker_env_snapshot": worker_env,
        "host_ollama_base_url": host_base_url,
        "host_ollama_version": host_version,
        "host_ollama_ps": host_ps,
        "docker_inference_state": inference_state,
    }
    if run_dir is not None:
        payload["run_dir"] = str(run_dir.relative_to(path.parent.parent))
    if probe_path is not None:
        payload["probe_result"] = str(probe_path.relative_to(path.parent.parent))
    _write_json(path, payload)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the strict host-Metal Gemma 4 backend swap experiment.")
    parser.add_argument("--env-file", default=DEFAULT_ENV_FILE)
    parser.add_argument("--catalog-file", default=DEFAULT_CATALOG_FILE)
    parser.add_argument("--control-model", default="gemma-3-270m-custom")
    parser.add_argument("--treatment-model", default="gemma4:e2b")
    parser.add_argument("--results-root", default=DEFAULT_RESULTS_ROOT)
    parser.add_argument("--run-prefix", default="gemma4_host_metal_strict_swap_v1")
    parser.add_argument("--ollama-binary", default="ollama")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = os.getcwd()
    env_file = Path(repo_root) / args.env_file
    base_env = _load_env_file(env_file)
    host_base_url = (base_env.get("HOST_OLLAMA_BASE_URL") or "http://localhost:11434").strip()
    commit_sha = _git_sha(repo_root)
    root = Path(repo_root) / args.results_root / f"{args.run_prefix}_{_utc_stamp()}"
    root.mkdir(parents=True, exist_ok=False)

    host_version = _host_ollama_version(args.ollama_binary)
    host_tags = _host_tags(host_base_url)
    _assert_host_model_available(host_tags, args.control_model)
    _assert_host_model_available(host_tags, args.treatment_model)
    _write_json(root / "host_tags.json", host_tags)

    manifest = {
        "commit_sha": commit_sha,
        "env_file": args.env_file,
        "catalog_file": args.catalog_file,
        "control_model": args.control_model,
        "treatment_model": args.treatment_model,
        "host_ollama_base_url": host_base_url,
        "docker_inference_expected_running": False,
    }
    _write_json(root / "experiment_manifest.json", manifest)

    control_env = _compose_env(base_env, model=args.control_model)
    _stop_inference(repo_root)
    control_inference_state = _assert_inference_stopped(repo_root)
    _compose_up_without_inference(repo_root, env_file=args.env_file, env=control_env)
    control_worker_env = _worker_env_snapshot(repo_root)
    _assert_worker_base_url(control_worker_env, base_env["LOCAL_AI_HTTP_BASE_URL"])
    _worker_healthcheck(repo_root, env=control_env)
    control_probe_run_id = f"{args.run_prefix}_control_probe_{_utc_stamp()}"
    control_probe_path = _probe(repo_root, model=args.control_model, run_id=control_probe_run_id, api_base_url=host_base_url)
    control_host_ps = _host_ollama_ps(args.ollama_binary, base_url=host_base_url)
    control_run_id = f"{args.run_prefix}_control_{_utc_stamp()}"
    control_run_dir = _run_ab(
        repo_root,
        arm="A",
        catalog_file=args.catalog_file,
        run_id=control_run_id,
        model=args.control_model,
        env=control_env,
    )
    _write_run_artifact(
        root / "control_snapshot.json",
        label="control",
        model=args.control_model,
        commit_sha=commit_sha,
        worker_env=control_worker_env,
        host_base_url=host_base_url,
        host_version=host_version,
        inference_state=control_inference_state,
        host_ps=control_host_ps,
        run_dir=control_run_dir,
        probe_path=control_probe_path,
    )

    treatment_env = _compose_env(base_env, model=args.treatment_model)
    _stop_inference(repo_root)
    treatment_inference_state = _assert_inference_stopped(repo_root)
    _compose_up_without_inference(repo_root, env_file=args.env_file, env=treatment_env)
    treatment_worker_env = _worker_env_snapshot(repo_root)
    _assert_worker_base_url(treatment_worker_env, base_env["LOCAL_AI_HTTP_BASE_URL"])
    _worker_healthcheck(repo_root, env=treatment_env)
    treatment_probe_run_id = f"{args.run_prefix}_treatment_probe_{_utc_stamp()}"
    treatment_probe_path = _probe(repo_root, model=args.treatment_model, run_id=treatment_probe_run_id, api_base_url=host_base_url)
    treatment_host_ps = _host_ollama_ps(args.ollama_binary, base_url=host_base_url)
    treatment_run_id = f"{args.run_prefix}_treatment_{_utc_stamp()}"
    treatment_run_dir = _run_ab(
        repo_root,
        arm="B",
        catalog_file=args.catalog_file,
        run_id=treatment_run_id,
        model=args.treatment_model,
        env=treatment_env,
    )
    _write_run_artifact(
        root / "treatment_snapshot.json",
        label="treatment",
        model=args.treatment_model,
        commit_sha=commit_sha,
        worker_env=treatment_worker_env,
        host_base_url=host_base_url,
        host_version=host_version,
        inference_state=treatment_inference_state,
        host_ps=treatment_host_ps,
        run_dir=treatment_run_dir,
        probe_path=treatment_probe_path,
    )

    print(json.dumps({"experiment_dir": str(root), **manifest}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shlex
import subprocess
from typing import Any


DEFAULT_RESULTS_ROOT = "experiments/results"
DEFAULT_ENV_FILE = "env/profiles/gemma4_e2b_second_tier.env"
DEFAULT_CATALOG_FILE = "experiments/ab_catalogs_v1.txt"


def _run(cmd: list[str], *, cwd: str | None = None, env: dict[str, str] | None = None, capture: bool = False) -> subprocess.CompletedProcess[str]:
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


def _compose_up(repo_root: str, *, env_file: str, env: dict[str, str]) -> None:
    _run(
        [
            "docker",
            "compose",
            "--env-file",
            env_file,
            "up",
            "-d",
            "--force-recreate",
            "inference",
            "worker",
            "api",
            "pipeline",
        ],
        cwd=repo_root,
        env=env,
    )


def _inspect_inference_memory(repo_root: str) -> dict[str, int]:
    out = _run(
        [
            "docker",
            "inspect",
            "town-council-inference-1",
            "--format",
            "{{.HostConfig.Memory}} {{.HostConfig.MemorySwap}}",
        ],
        cwd=repo_root,
        capture=True,
    ).stdout.strip()
    mem, swap = out.split()
    return {"memory_bytes": int(mem), "memory_swap_bytes": int(swap)}


def _assert_inference_memory(memory_snapshot: dict[str, int], expected_limit: str) -> None:
    normalized = expected_limit.strip().upper()
    multiplier = 1
    if normalized.endswith("G"):
        multiplier = 1024 * 1024 * 1024
        value = normalized[:-1]
    elif normalized.endswith("M"):
        multiplier = 1024 * 1024
        value = normalized[:-1]
    else:
        value = normalized
    expected_bytes = int(value) * multiplier
    actual = int(memory_snapshot["memory_bytes"])
    if actual != expected_bytes:
        raise RuntimeError(
            f"inference memory cap mismatch: expected {expected_bytes} bytes from INFERENCE_MEM_LIMIT={expected_limit}, got {actual}"
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
            "keys=['LOCAL_AI_BACKEND','LOCAL_AI_HTTP_PROFILE','LOCAL_AI_HTTP_MODEL',"
            "'LOCAL_AI_HTTP_TIMEOUT_SECONDS','LOCAL_AI_HTTP_TIMEOUT_SEGMENT_SECONDS',"
            "'LOCAL_AI_HTTP_TIMEOUT_SUMMARY_SECONDS','LOCAL_AI_HTTP_TIMEOUT_TOPICS_SECONDS',"
            "'LOCAL_AI_HTTP_MAX_RETRIES','WORKER_CONCURRENCY','WORKER_POOL','OLLAMA_NUM_PARALLEL']; "
            "print(json.dumps({k: os.getenv(k, '') for k in keys}, sort_keys=True))"
        ),
    ]
    out = _run(cmd, cwd=repo_root, capture=True).stdout.strip()
    return json.loads(out)


def _probe(repo_root: str, *, model: str, run_id: str) -> Path:
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
            "scripts/probe_local_model_candidate.py",
            "--candidate",
            model,
            "--api-base-url",
            "http://inference:11434",
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
    env_snapshot: dict[str, str],
    memory_snapshot: dict[str, int],
    run_dir: Path | None = None,
    probe_path: Path | None = None,
) -> None:
    payload: dict[str, Any] = {
        "label": label,
        "model": model,
        "commit_sha": commit_sha,
        "env_snapshot": env_snapshot,
        "inference_memory": memory_snapshot,
    }
    if run_dir is not None:
        payload["run_dir"] = str(run_dir.relative_to(path.parent.parent))
    if probe_path is not None:
        payload["probe_result"] = str(probe_path.relative_to(path.parent.parent))
    _write_json(path, payload)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the declared Gemma 4 second-tier profile verification experiment.")
    parser.add_argument("--env-file", default=DEFAULT_ENV_FILE)
    parser.add_argument("--catalog-file", default=DEFAULT_CATALOG_FILE)
    parser.add_argument("--control-model", default="gemma-3-270m-custom")
    parser.add_argument("--treatment-model", default="gemma4:e2b")
    parser.add_argument("--results-root", default=DEFAULT_RESULTS_ROOT)
    parser.add_argument("--run-prefix", default="gemma4_profile_verification_v2")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = os.getcwd()
    env_file = Path(repo_root) / args.env_file
    base_env = _load_env_file(env_file)
    commit_sha = _git_sha(repo_root)
    root = Path(repo_root) / args.results_root / f"{args.run_prefix}_{_utc_stamp()}"
    root.mkdir(parents=True, exist_ok=False)

    manifest = {
        "commit_sha": commit_sha,
        "env_file": args.env_file,
        "catalog_file": args.catalog_file,
        "control_model": args.control_model,
        "treatment_model": args.treatment_model,
    }
    _write_json(root / "experiment_manifest.json", manifest)

    control_env = _compose_env(base_env, model=args.control_model)
    _compose_up(repo_root, env_file=args.env_file, env=control_env)
    control_memory = _inspect_inference_memory(repo_root)
    _assert_inference_memory(control_memory, base_env["INFERENCE_MEM_LIMIT"])
    control_worker_env = _worker_env_snapshot(repo_root)
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
        env_snapshot=control_worker_env,
        memory_snapshot=control_memory,
        run_dir=control_run_dir,
    )

    treatment_env = _compose_env(base_env, model=args.treatment_model)
    _compose_up(repo_root, env_file=args.env_file, env=treatment_env)
    treatment_memory = _inspect_inference_memory(repo_root)
    _assert_inference_memory(treatment_memory, base_env["INFERENCE_MEM_LIMIT"])
    treatment_worker_env = _worker_env_snapshot(repo_root)
    probe_run_id = f"{args.run_prefix}_probe_{_utc_stamp()}"
    probe_path = _probe(repo_root, model=args.treatment_model, run_id=probe_run_id)
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
        env_snapshot=treatment_worker_env,
        memory_snapshot=treatment_memory,
        run_dir=treatment_run_dir,
        probe_path=probe_path,
    )

    print(json.dumps({"experiment_dir": str(root), **manifest}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

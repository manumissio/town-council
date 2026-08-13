from __future__ import annotations

from pathlib import Path
import re
import subprocess


WORKER_PROFILE_KEYS = (
    "LOCAL_AI_BACKEND",
    "LOCAL_AI_HTTP_API",
    "LOCAL_AI_HTTP_PROFILE",
    "LOCAL_AI_HTTP_MODEL",
    "LOCAL_AI_HTTP_TIMEOUT_SECONDS",
    "LOCAL_AI_HTTP_TIMEOUT_SEGMENT_SECONDS",
    "LOCAL_AI_HTTP_TIMEOUT_SUMMARY_SECONDS",
    "LOCAL_AI_HTTP_TIMEOUT_TOPICS_SECONDS",
    "LOCAL_AI_HTTP_MAX_RETRIES",
    "WORKER_CONCURRENCY",
    "WORKER_POOL",
)
INFERENCE_PROFILE_KEYS = ("OLLAMA_NUM_PARALLEL",)
SEMANTIC_PROFILE_KEYS = (
    "SEMANTIC_BACKEND",
    "SEMANTIC_CONTENT_MAX_CHARS",
    "SEMANTIC_ENABLED",
    "SEMANTIC_MODEL_NAME",
)


def _container_environment(service: str, keys: tuple[str, ...], repo_root: Path) -> dict[str, str]:
    completed = subprocess.run(
        ["docker", "compose", "exec", "-T", service, "env"],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )
    environment = dict(
        line.split("=", 1)
        for line in completed.stdout.splitlines()
        if "=" in line
    )
    return {key: environment[key] for key in keys if key in environment}


def _service_command(service: str, repo_root: Path) -> str:
    completed = subprocess.run(
        ["docker", "compose", "exec", "-T", service, "cat", "/proc/1/cmdline"],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )
    return " ".join(part for part in completed.stdout.split("\0") if part).strip()


def capture_runtime_profile(repo_root: Path) -> dict[str, str]:
    profile = _container_environment("worker", WORKER_PROFILE_KEYS, repo_root)
    profile.update(_container_environment("inference", INFERENCE_PROFILE_KEYS, repo_root))
    profile.update(_container_environment("semantic-worker", SEMANTIC_PROFILE_KEYS, repo_root))
    worker_command = _service_command("worker", repo_root)
    profile["WORKER_PROCESS_COMMAND"] = worker_command
    profile["SEMANTIC_WORKER_PROCESS_COMMAND"] = _service_command("semantic-worker", repo_root)
    for profile_key, command_flag in (("WORKER_CONCURRENCY", "concurrency"), ("WORKER_POOL", "pool")):
        match = re.search(rf"--{command_flag}=(?P<value>[^\s]+)", worker_command)
        if match:
            profile[profile_key] = match.group("value")
    return profile


def git_commit(repo_root: Path) -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=repo_root, text=True
    ).strip()


def tracked_tree_clean(repo_root: Path) -> bool:
    unstaged = subprocess.run(["git", "diff", "--quiet"], cwd=repo_root, check=False)
    staged = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=repo_root, check=False)
    return unstaged.returncode == 0 and staged.returncode == 0


def tracked_manifest_bytes(manifest_path: Path, repo_root: Path) -> tuple[str, bytes]:
    resolved_path = manifest_path.resolve(strict=True)
    manifests_root = (repo_root / "profiling" / "manifests").resolve(strict=True)
    if manifest_path.is_symlink() or not resolved_path.is_file() or not resolved_path.is_relative_to(manifests_root):
        raise ValueError("baseline manifest must be a regular file under profiling/manifests")
    relative_path = resolved_path.relative_to(repo_root.resolve())
    completed = subprocess.run(
        ["git", "show", f"HEAD:{relative_path.as_posix()}"],
        cwd=repo_root,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise ValueError("baseline manifest must be tracked at HEAD")
    working_bytes = resolved_path.read_bytes()
    if completed.stdout != working_bytes:
        raise ValueError("baseline manifest bytes differ from HEAD")
    return relative_path.as_posix(), working_bytes


def tracked_expected_baseline_bytes(expected_path: Path, repo_root: Path) -> bytes:
    resolved_path = expected_path.resolve(strict=True)
    baselines_root = (repo_root / "profiling" / "baselines").resolve(strict=True)
    if expected_path.is_symlink() or not resolved_path.is_file() or not resolved_path.is_relative_to(baselines_root):
        raise ValueError("expected baseline must be a regular file under profiling/baselines")
    relative_path = resolved_path.relative_to(repo_root.resolve())
    completed = subprocess.run(
        ["git", "show", f":{relative_path.as_posix()}"],
        cwd=repo_root,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise ValueError("expected baseline must be tracked in the Git index")
    working_bytes = resolved_path.read_bytes()
    if completed.stdout != working_bytes:
        raise ValueError("expected baseline bytes differ from the Git index")
    return working_bytes

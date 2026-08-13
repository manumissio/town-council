from pathlib import Path
import subprocess

import pytest

from scripts import profile_pipeline_runtime as runtime


def test_capture_runtime_profile_reads_worker_and_inference_containers(monkeypatch, tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def _run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        if command[-2:] == ["cat", "/proc/1/cmdline"]:
            task_module = "pipeline.semantic_tasks" if "semantic-worker" in command else "pipeline.tasks"
            payload = f"celery\0-A\0{task_module}\0--concurrency=3\0--pool=prefork\0"
        elif "semantic-worker" in command:
            payload = "SEMANTIC_ENABLED=true\n"
        elif "worker" in command:
            payload = "LOCAL_AI_BACKEND=http\n"
        else:
            payload = "OLLAMA_NUM_PARALLEL=1\n"
        return subprocess.CompletedProcess(command, 0, stdout=payload, stderr="")

    monkeypatch.setattr(runtime.subprocess, "run", _run)

    assert runtime.capture_runtime_profile(tmp_path) == {
        "LOCAL_AI_BACKEND": "http",
        "OLLAMA_NUM_PARALLEL": "1",
        "SEMANTIC_ENABLED": "true",
        "SEMANTIC_WORKER_PROCESS_COMMAND": "celery -A pipeline.semantic_tasks --concurrency=3 --pool=prefork",
        "WORKER_CONCURRENCY": "3",
        "WORKER_POOL": "prefork",
        "WORKER_PROCESS_COMMAND": "celery -A pipeline.tasks --concurrency=3 --pool=prefork",
    }
    assert [command[4] for command in calls] == [
        "worker",
        "inference",
        "semantic-worker",
        "worker",
        "semantic-worker",
    ]


def test_tracked_manifest_rejects_untracked_or_modified_files(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    manifest = repo / "profiling" / "manifests" / "baseline.txt"
    manifest.parent.mkdir(parents=True)
    manifest.write_text("1\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(repo)], check=True)

    with pytest.raises(ValueError, match="tracked at HEAD"):
        runtime.tracked_manifest_bytes(manifest, repo)

    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "manifest"],
        check=True,
    )
    relative_path, manifest_bytes = runtime.tracked_manifest_bytes(manifest, repo)
    assert relative_path == "profiling/manifests/baseline.txt"
    assert manifest_bytes == b"1\n"

    manifest.write_text("2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="differ from HEAD"):
        runtime.tracked_manifest_bytes(manifest, repo)


def test_tracked_expected_baseline_rejects_untracked_or_modified_files(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    expected_baseline = repo / "profiling" / "baselines" / "baseline.json"
    expected_baseline.parent.mkdir(parents=True)
    expected_baseline.write_text("{}\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(repo)], check=True)

    with pytest.raises(ValueError, match="tracked in the Git index"):
        runtime.tracked_expected_baseline_bytes(expected_baseline, repo)

    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    assert runtime.tracked_expected_baseline_bytes(expected_baseline, repo) == b"{}\n"

    expected_baseline.write_text('{"changed": true}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="differ from the Git index"):
        runtime.tracked_expected_baseline_bytes(expected_baseline, repo)

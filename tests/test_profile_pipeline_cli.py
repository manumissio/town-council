import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

from scripts.profile_pipeline_validation import BaselineValidation
from scripts import profile_pipeline_runner as runner


spec = importlib.util.spec_from_file_location("profile_pipeline", Path("scripts/profile_pipeline.py"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


PROFILE_PIPELINE_SCRIPT = Path("scripts/profile_pipeline.py")


def _run_profile_cli(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(PROFILE_PIPELINE_SCRIPT), *arguments],
        capture_output=True,
        text=True,
        check=False,
    )


def test_profile_pipeline_requires_manifest_for_baseline(tmp_path: Path):
    try:
        mod.main(["--mode", "baseline", "--output-dir", str(tmp_path), "--diagnostic"])
    except SystemExit as exc:
        assert "--manifest is required for baseline mode" in str(exc)
    else:
        raise AssertionError("expected SystemExit")


def test_terminal_wait_stops_after_failed_task_reaches_terminal_state(monkeypatch, tmp_path: Path) -> None:
    (tmp_path / "spans.jsonl").write_text(
        "\n".join(
            json.dumps(profile_event)
            for profile_event in (
                {
                    "event_type": "task_dispatch",
                    "boundary": "before",
                    "task_id": "failed-task",
                    "retry_ordinal": 0,
                },
                {
                    "event_type": "task_dispatch",
                    "boundary": "after",
                    "task_id": "failed-task",
                    "retry_ordinal": 0,
                },
                {
                    "event_type": "task_start",
                    "task_id": "failed-task",
                    "execution_id": "failed-attempt",
                    "retry_ordinal": 0,
                },
                {
                    "event_type": "task_span",
                    "task_id": "failed-task",
                    "execution_id": "failed-attempt",
                    "retry_ordinal": 0,
                    "outcome": "failure",
                },
            )
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(runner, "TASK_POLL_SECONDS", 0.0)
    monkeypatch.setattr(runner, "TASK_QUIET_SECONDS", 0.0)

    runner._wait_for_terminal_tasks(tmp_path)


def test_profile_pipeline_rejects_diagnostic_for_triage(tmp_path: Path):
    with pytest.raises(SystemExit, match="--diagnostic is only supported for baseline mode"):
        mod.main(["--mode", "triage", "--output-dir", str(tmp_path), "--diagnostic"])


def test_profile_pipeline_writes_manifest_and_result(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(mod, "_select_triage_catalog_ids_via_docker", lambda limit, city: {"catalog_ids": [11, 12], "catalog_count": 2})
    monkeypatch.setattr(mod, "_provider_counters_before_run", lambda: {"provider_requests_total": 1.0, "provider_timeouts_total": 0.0, "provider_retries_total": 0.0})
    monkeypatch.setattr("scripts.profile_pipeline_runner.git_commit", lambda _root: "abc123")
    monkeypatch.setattr("scripts.profile_pipeline_runner.tracked_tree_clean", lambda _root: True)
    monkeypatch.setattr("scripts.profile_pipeline_runner._wait_for_terminal_tasks", lambda _run_dir: None)
    commands = []

    def _fake_run(command, **kwargs):
        commands.append((command, kwargs))
        return type("Completed", (), {"returncode": 0})()

    monkeypatch.setattr(mod.subprocess, "run", _fake_run)
    exit_code = mod.main(["--mode", "triage", "--output-dir", str(tmp_path), "--skip-batch"])

    run_dirs = list(tmp_path.iterdir())
    assert exit_code == 0
    assert len(run_dirs) == 1
    manifest = json.loads((run_dirs[0] / "run_manifest.json").read_text(encoding="utf-8"))
    result = json.loads((run_dirs[0] / "result.json").read_text(encoding="utf-8"))
    assert manifest["catalog_ids"] == [11, 12]
    assert manifest["workload_only"] is True
    assert result["status"] == "completed"
    assert result["profile"]["workload_only"] is True
    assert result["totals"]["core_elapsed_seconds"] is not None
    assert result["totals"]["batch_elapsed_seconds"] is None
    assert result["totals"]["combined_elapsed_seconds"] >= result["totals"]["core_elapsed_seconds"]
    assert result["segments"][0]["name"] == "pipeline"
    assert any("TC_PROFILE_WORKLOAD_ONLY=1" in " ".join(cmd) for cmd, _ in commands)
    assert any("collect_soak_metrics.py" in " ".join(cmd) for cmd, _ in commands)


@pytest.mark.parametrize("extra_arguments", [("--skip-batch",), ("--compare-to", "expected.json")])
def test_profile_pipeline_rejects_invalid_bare_baseline_contract_before_artifact_creation(
    tmp_path: Path,
    extra_arguments: tuple[str, ...],
):
    output_dir = tmp_path / "profiles"
    completed = _run_profile_cli(
        "--mode",
        "baseline",
        "--manifest",
        str(tmp_path / "missing.txt"),
        "--output-dir",
        str(output_dir),
        *extra_arguments,
    )

    assert completed.returncode != 0
    assert "baseline profiling requires batch enrichment" in completed.stderr or "comparison after capture" in completed.stderr
    assert not output_dir.exists()


def test_profile_pipeline_diagnostic_allows_untracked_manifest(
    tmp_path: Path,
):
    output_dir = tmp_path / "profiles"
    completed = _run_profile_cli(
        "--mode",
        "baseline",
        "--manifest",
        str(tmp_path / "missing.txt"),
        "--output-dir",
        str(output_dir),
        "--diagnostic",
    )

    assert completed.returncode != 0
    assert "No such file or directory" in completed.stderr
    assert not output_dir.exists()


def test_profile_pipeline_diagnostic_baseline_is_non_promotional(monkeypatch, tmp_path: Path):
    manifest_path = tmp_path / "baseline_demo.txt"
    manifest_path.write_text("21\n", encoding="utf-8")
    monkeypatch.setattr(mod, "_provider_counters_before_run", lambda: None)
    monkeypatch.setattr(
        "scripts.profile_pipeline_runner.capture_runtime_profile",
        lambda _root: {"LOCAL_AI_BACKEND": "http"},
    )
    monkeypatch.setattr("scripts.profile_pipeline_runner.git_commit", lambda _root: "abc123")
    monkeypatch.setattr("scripts.profile_pipeline_runner.tracked_tree_clean", lambda _root: True)
    monkeypatch.setattr("scripts.profile_pipeline_runner._wait_for_terminal_tasks", lambda _run_dir: None)
    commands = []

    def _fake_run(command, **kwargs):
        commands.append((command, kwargs))
        return type("Completed", (), {"returncode": 0})()

    monkeypatch.setattr(mod.subprocess, "run", _fake_run)

    exit_code = mod.main(
        [
            "--mode",
            "baseline",
            "--manifest",
            str(manifest_path),
            "--output-dir",
            str(tmp_path),
            "--diagnostic",
        ]
    )

    run_dirs = [path for path in tmp_path.iterdir() if path.is_dir()]
    run_manifest = json.loads((run_dirs[0] / "run_manifest.json").read_text(encoding="utf-8"))
    result_manifest = json.loads((run_dirs[0] / "result.json").read_text(encoding="utf-8"))
    profile_commands = [command for command, _ in commands if "run_pipeline.py" in command or "run_batch_enrichment.py" in command]

    assert exit_code == 0
    assert run_manifest["baseline_valid"] is False
    assert run_manifest["baseline_validation_reasons"][0] == "diagnostic_run"
    assert "baseline_valid" not in result_manifest
    assert [command[-1] for command in profile_commands] == ["run_pipeline.py", "run_batch_enrichment.py"]
    assert all(not any(value.startswith("TC_PROFILE_BASELINE_VALID=") for value in command) for command in profile_commands)
    assert not any("db_migrate.py" in command or "backfill_catalog_hashes.py" in command for command, _ in commands)


@pytest.mark.parametrize(
    ("validation", "expected_valid", "expected_error"),
    [
        (BaselineValidation(True, (), ()), True, None),
        (
            BaselineValidation(False, ("provider_deltas_incomplete",), ()),
            False,
            "baseline evidence invalid: provider_deltas_incomplete",
        ),
    ],
)
def test_bare_baseline_promotes_only_from_terminal_validation(
    monkeypatch,
    tmp_path: Path,
    validation: BaselineValidation,
    expected_valid: bool,
    expected_error: str | None,
) -> None:
    manifest_path = tmp_path / "baseline_demo.txt"
    manifest_path.write_text("21\n", encoding="utf-8")
    runtime_profile = {
        "LOCAL_AI_BACKEND": "http",
        "WORKER_PROCESS_COMMAND": "celery --concurrency=3 --pool=prefork",
    }
    monkeypatch.setattr(mod, "_provider_counters_before_run", lambda: None)
    monkeypatch.setattr(
        "scripts.profile_pipeline_runner.tracked_manifest_bytes",
        lambda _path, _root: ("profiling/manifests/baseline_demo.txt", b"21\n"),
    )
    monkeypatch.setattr("scripts.profile_pipeline_runner.capture_runtime_profile", lambda _root: runtime_profile)
    monkeypatch.setattr("scripts.profile_pipeline_runner._runtime_profile_unchanged", lambda *_args: True)
    monkeypatch.setattr("scripts.profile_pipeline_runner.git_commit", lambda _root: "abc123")
    monkeypatch.setattr("scripts.profile_pipeline_runner.tracked_tree_clean", lambda _root: True)
    monkeypatch.setattr("scripts.profile_pipeline_runner._wait_for_terminal_tasks", lambda _run_dir: None)
    monkeypatch.setattr("scripts.profile_pipeline_runner.validate_profile_artifacts", lambda *_args, **_kwargs: validation)
    monkeypatch.setattr(mod.subprocess, "run", lambda *_args, **_kwargs: type("Completed", (), {"returncode": 0})())

    arguments = [
        "--mode",
        "baseline",
        "--manifest",
        str(manifest_path),
        "--output-dir",
        str(tmp_path / "profiles"),
        "--run-id",
        "terminal-validation",
    ]
    if expected_error is None:
        assert mod.main(arguments) == 0
    else:
        with pytest.raises(RuntimeError, match=expected_error):
            mod.main(arguments)

    run_dir = tmp_path / "profiles" / "terminal-validation"
    run_manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    result_manifest = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
    assert run_manifest["baseline_valid"] is expected_valid
    assert "baseline_valid" not in result_manifest
    if expected_error is not None:
        assert result_manifest["status"] == "failed"
        assert "provider_deltas_incomplete" in run_manifest["baseline_validation_reasons"]


def test_profile_pipeline_rejects_retired_dry_run_prepare_flag(tmp_path: Path):
    completed = _run_profile_cli(
        "--mode",
        "baseline",
        "--manifest",
        str(tmp_path / "baseline_demo.txt"),
        "--diagnostic",
        "--dry-run-prepare",
    )

    assert completed.returncode == 2
    assert "unrecognized arguments: --dry-run-prepare" in completed.stderr


def test_profile_pipeline_rejects_sidecar_before_run_directory(tmp_path: Path):
    manifest_path = tmp_path / "baseline_demo.txt"
    manifest_path.write_text("21\n22\n", encoding="utf-8")
    manifest_path.with_suffix(".json").write_text("{}\n", encoding="utf-8")

    with pytest.raises(SystemExit, match="synthetic replay packages are retired"):
        mod.main(
            [
                "--mode",
                "baseline",
                "--manifest",
                str(manifest_path),
                "--output-dir",
                str(tmp_path),
                "--run-id",
                "retired-sidecar",
                "--skip-batch",
                "--diagnostic",
            ]
        )

    assert not (tmp_path / "retired-sidecar").exists()

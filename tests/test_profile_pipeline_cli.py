import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest


spec = importlib.util.spec_from_file_location("profile_pipeline", Path("scripts/profile_pipeline.py"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


PROFILE_PIPELINE_SCRIPT = Path("scripts/profile_pipeline.py")
BASELINE_QUARANTINE_PHRASE = "promotion-grade baseline execution is quarantined"


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


def test_profile_pipeline_rejects_diagnostic_for_triage(tmp_path: Path):
    with pytest.raises(SystemExit, match="--diagnostic is only supported for baseline mode"):
        mod.main(["--mode", "triage", "--output-dir", str(tmp_path), "--diagnostic"])


def test_profile_pipeline_writes_manifest_and_result(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(mod, "_select_triage_catalog_ids_via_docker", lambda limit, city: {"catalog_ids": [11, 12], "catalog_count": 2})
    monkeypatch.setattr(mod, "_provider_counters_before_run", lambda: {"provider_requests_total": 1.0, "provider_timeouts_total": 0.0, "provider_retries_total": 0.0})
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


@pytest.mark.parametrize("extra_arguments", [(), ("--compare-to", "expected.json")])
def test_profile_pipeline_quarantines_bare_baseline_before_artifact_creation(
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
    assert BASELINE_QUARANTINE_PHRASE in completed.stderr
    assert not output_dir.exists()


@pytest.mark.parametrize("allowed_argument", ["--diagnostic", "--dry-run-prepare"])
def test_profile_pipeline_quarantine_allows_non_promotional_baseline_paths(
    tmp_path: Path,
    allowed_argument: str,
):
    output_dir = tmp_path / "profiles"
    completed = _run_profile_cli(
        "--mode",
        "baseline",
        "--manifest",
        str(tmp_path / "missing.txt"),
        "--output-dir",
        str(output_dir),
        allowed_argument,
    )

    assert completed.returncode != 0
    assert BASELINE_QUARANTINE_PHRASE not in completed.stderr
    assert "No such file or directory" in completed.stderr
    assert not output_dir.exists()


def test_profile_pipeline_diagnostic_baseline_is_non_promotional(monkeypatch, tmp_path: Path):
    manifest_path = tmp_path / "baseline_demo.txt"
    manifest_path.write_text("21\n", encoding="utf-8")
    manifest_path.with_suffix(".json").write_text(
        json.dumps(
            {
                "schema_version": 3,
                "manifest_name": "baseline_demo",
                "catalog_ids": [21],
                "strata": {"extract": [21], "segment": [], "summary": [], "entity": [], "org": []},
                "extract_source_sha256": {"21": "a" * 64},
                "expected_phase_coverage": {"extract": 1, "segment": 0, "summary": 0, "entity": 0, "org": 0},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "_provider_counters_before_run", lambda: None)
    monkeypatch.setattr(
        mod,
        "_prepare_manifest_package_via_docker",
        lambda manifest_rel, dry_run: {
            "dry_run": dry_run,
            "report": {"catalog_count": 1},
            "applied": {"cleared_summary_catalogs": 0},
        },
    )
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
    hash_backfill_commands = [command for command, _ in commands if "pipeline/backfill_catalog_hashes.py" in command]

    assert exit_code == 0
    assert run_manifest["baseline_valid"] is False
    assert result_manifest["baseline_valid"] is False
    assert [command[-1] for command in profile_commands] == ["run_pipeline.py", "run_batch_enrichment.py"]
    assert all("TC_PROFILE_BASELINE_VALID=0" in command for command in profile_commands)
    assert len(hash_backfill_commands) == 1
    assert any(
        value.startswith("TC_PROFILE_CATALOG_MANIFEST=") and value.endswith("/catalog_manifest.txt")
        for value in hash_backfill_commands[0]
    )


def test_profile_pipeline_dry_run_prepare_requires_manifest_package(monkeypatch, tmp_path: Path):
    manifest_path = tmp_path / "baseline_demo.txt"
    manifest_path.write_text("21\n22\n", encoding="utf-8")

    try:
        mod.main(["--mode", "baseline", "--manifest", str(manifest_path), "--output-dir", str(tmp_path), "--dry-run-prepare"])
    except SystemExit as exc:
        assert "requires a manifest package sidecar" in str(exc)
    else:
        raise AssertionError("expected SystemExit")


@pytest.mark.parametrize(
    "manifest_package",
    [
        {
            "schema_version": 1,
            "manifest_name": "baseline_demo",
            "catalog_ids": [21, 22],
        },
        {
            "schema_version": 3,
            "manifest_name": "baseline_demo",
            "catalog_ids": [21, 22],
            "strata": {"extract": [21], "segment": [22], "summary": [], "entity": [], "org": []},
            "extract_source_sha256": {},
            "expected_phase_coverage": {"extract": 1, "segment": 1, "summary": 0, "entity": 0, "org": 0},
        },
    ],
)
def test_profile_pipeline_rejects_invalid_manifest_package_without_run_directory(
    tmp_path: Path,
    manifest_package: dict,
):
    manifest_path = tmp_path / "baseline_demo.txt"
    manifest_path.write_text("21\n22\n", encoding="utf-8")
    manifest_path.with_suffix(".json").write_text(
        json.dumps(manifest_package),
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        mod.main(
            [
                "--mode",
                "baseline",
                "--manifest",
                str(manifest_path),
                "--output-dir",
                str(tmp_path),
                "--run-id",
                "invalid-package",
                "--skip-batch",
                "--diagnostic",
            ]
        )

    assert not (tmp_path / "invalid-package").exists()

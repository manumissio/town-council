import json
import os
import subprocess
from pathlib import Path


def test_onboarding_runner_subset_and_runs_emit_artifacts(tmp_path):
    run_id = "test_run"
    output_dir = tmp_path / "city_onboarding"

    env = os.environ.copy()
    env["DRY_RUN"] = "1"

    cmd = [
        "bash",
        "scripts/onboard_city_wave.sh",
        "wave1",
        "--cities",
        "hayward,san_mateo",
        "--runs",
        "3",
        "--run-id",
        run_id,
        "--output-dir",
        str(output_dir),
    ]
    result = subprocess.run(cmd, text=True, capture_output=True, env=env, check=True)

    assert "Completed dry-run wave plan" in result.stdout
    runs_path = output_dir / run_id / "runs.jsonl"
    assert runs_path.exists()

    rows = [json.loads(line) for line in runs_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) == 6
    assert {row["city"] for row in rows} == {"hayward", "san_mateo"}
    assert {row["run_index"] for row in rows} == {1, 2, 3}


def test_onboarding_runner_rejects_unknown_city(tmp_path):
    run_id = "bad_city"
    output_dir = tmp_path / "city_onboarding"

    env = os.environ.copy()
    env["DRY_RUN"] = "1"

    cmd = [
        "bash",
        "scripts/onboard_city_wave.sh",
        "wave1",
        "--cities",
        "hayward,not_a_city",
        "--run-id",
        run_id,
        "--output-dir",
        str(output_dir),
    ]
    result = subprocess.run(cmd, text=True, capture_output=True, env=env)
    assert result.returncode == 2
    assert "is not in wave1" in result.stdout or "is not in wave1" in result.stderr

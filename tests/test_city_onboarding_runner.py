import json
import os
import subprocess
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from pipeline.models import Base


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
    assert "using rollout registry: city_metadata/city_rollout_registry.csv" in result.stdout
    assert "scripts/segment_city_corpus.py --city hayward" in result.stdout
    assert "scripts/segment_city_corpus.py --city san_mateo" in result.stdout
    assert "PIPELINE_ONBOARDING_CITY=hayward" in result.stdout
    assert "PIPELINE_ONBOARDING_CITY=san_mateo" in result.stdout
    assert "PIPELINE_ONBOARDING_DOCUMENT_CHUNK_SIZE=5" in result.stdout
    assert "PIPELINE_ONBOARDING_MAX_WORKERS=1" in result.stdout
    assert "TIKA_OCR_FALLBACK_ENABLED=false" in result.stdout
    runs_path = output_dir / run_id / "runs.jsonl"
    assert runs_path.exists()

    rows = [json.loads(line) for line in runs_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) == 6
    assert {row["city"] for row in rows} == {"hayward", "san_mateo"}
    assert {row["run_index"] for row in rows} == {1, 2, 3}
    assert {row["segmentation_status"] for row in rows} == {"success"}


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


def test_onboarding_runner_marks_empty_crawl_and_skips_downstream_steps(tmp_path):
    run_id = "empty_crawl"
    output_dir = tmp_path / "city_onboarding"
    output_dir.mkdir(parents=True, exist_ok=True)

    db_path = tmp_path / "crawler_empty.sqlite"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    sessionmaker(bind=engine)()
    engine.dispose()

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    docker_log = tmp_path / "docker.log"
    curl_log = tmp_path / "curl.log"

    docker_stub = """#!/usr/bin/env bash
set -euo pipefail
printf '%s\\n' "$*" >> "$DOCKER_LOG"
    if [[ "$*" == *"scrapy crawl fremont"* ]]; then
      exit 0
    fi
    if [[ "$*" == *"scripts/check_city_crawl_evidence.py"* ]]; then
      printf '%s\\n' '{"city": "fremont", "event_stage_count": 0, "has_evidence": false, "url_stage_count": 0}'
      exit 3
    fi
echo "unexpected docker invocation: $*" >&2
exit 99
"""
    curl_stub = """#!/usr/bin/env bash
set -euo pipefail
printf '%s\\n' "$*" >> "$CURL_LOG"
exit 0
"""

    docker_path = bin_dir / "docker"
    docker_path.write_text(docker_stub, encoding="utf-8")
    docker_path.chmod(0o755)
    curl_path = bin_dir / "curl"
    curl_path.write_text(curl_stub, encoding="utf-8")
    curl_path.chmod(0o755)

    env = os.environ.copy()
    env["DRY_RUN"] = "0"
    env["DATABASE_URL"] = f"sqlite:///{db_path}"
    env["DOCKER_LOG"] = str(docker_log)
    env["CURL_LOG"] = str(curl_log)
    env["PATH"] = f"{bin_dir}:{env['PATH']}"

    cmd = [
        "bash",
        "scripts/onboard_city_wave.sh",
        "wave1",
        "--cities",
        "fremont",
        "--runs",
        "1",
        "--run-id",
        run_id,
        "--output-dir",
        str(output_dir),
    ]
    result = subprocess.run(cmd, text=True, capture_output=True, env=env, check=True)

    rows = [
        json.loads(line)
        for line in (output_dir / run_id / "runs.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(rows) == 1
    row = rows[0]
    assert row["crawler_status"] == "failed"
    assert row["pipeline_status"] == "failed"
    assert row["segmentation_status"] == "failed"
    assert row["search_status"] == "failed"
    assert row["city"] == "fremont"
    assert row["error"] == "crawler_empty"
    assert '"has_evidence": false' in result.stdout
    assert "run_pipeline.py" not in docker_log.read_text(encoding="utf-8")
    assert "segment_city_corpus.py" not in docker_log.read_text(encoding="utf-8")
    assert not curl_log.exists()


def test_onboarding_runner_marks_stable_noop_for_prior_pass_city(tmp_path):
    run_id = "stable_noop"
    output_dir = tmp_path / "city_onboarding"
    output_dir.mkdir(parents=True, exist_ok=True)

    db_path = tmp_path / "stable_noop.sqlite"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    sessionmaker(bind=engine)()
    engine.dispose()

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    docker_log = tmp_path / "docker.log"

    docker_stub = """#!/usr/bin/env bash
set -euo pipefail
printf '%s\\n' \"$*\" >> \"$DOCKER_LOG\"
if [[ \"$*\" == *\"scrapy crawl hayward\"* ]]; then
  exit 0
fi
if [[ \"$*\" == *\"scripts/check_city_crawl_evidence.py\"* ]]; then
  printf '%s\\n' '{\"city\": \"hayward\", \"event_stage_count\": 0, \"has_evidence\": false, \"url_stage_count\": 0}'
  exit 3
fi
echo \"unexpected docker invocation: $*\" >&2
exit 99
"""

    docker_path = bin_dir / "docker"
    docker_path.write_text(docker_stub, encoding="utf-8")
    docker_path.chmod(0o755)

    env = os.environ.copy()
    env["DRY_RUN"] = "0"
    env["DATABASE_URL"] = f"sqlite:///{db_path}"
    env["DOCKER_LOG"] = str(docker_log)
    env["PATH"] = f"{bin_dir}:{env['PATH']}"

    cmd = [
        "bash",
        "scripts/onboard_city_wave.sh",
        "wave1",
        "--cities",
        "hayward",
        "--runs",
        "1",
        "--run-id",
        run_id,
        "--output-dir",
        str(output_dir),
    ]
    result = subprocess.run(cmd, text=True, capture_output=True, env=env, check=True)

    rows = [
        json.loads(line)
        for line in (output_dir / run_id / "runs.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(rows) == 1
    row = rows[0]
    assert row["crawler_status"] == "crawler_stable_noop"
    assert row["pipeline_status"] == "skipped"
    assert row["segmentation_status"] == "skipped"
    assert row["search_status"] == "skipped"
    assert row["overall_status"] == "success"
    assert row["error"] == "stable_delta_noop:city_wave1_hayward_sanmateo_20260313_210210"
    assert "stable delta no-op confirmation for hayward" in result.stdout
    assert "run_pipeline.py" not in docker_log.read_text(encoding="utf-8")
    assert "segment_city_corpus.py" not in docker_log.read_text(encoding="utf-8")

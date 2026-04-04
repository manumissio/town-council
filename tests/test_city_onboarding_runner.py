import json
import os
import subprocess
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from pipeline.models import Base, Event, Place


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
    assert {row["verification_mode"] for row in rows} == {"confirmation"}
    assert {row["state_reset_applied"] for row in rows} == {False}


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


def test_onboarding_runner_dry_run_first_time_city_keeps_reset_json_parseable(tmp_path):
    run_id = "dry_run_first_time"
    output_dir = tmp_path / "city_onboarding"

    env = os.environ.copy()
    env["DRY_RUN"] = "1"

    cmd = [
        "bash",
        "scripts/onboard_city_wave.sh",
        "wave1",
        "--cities",
        "fremont",
        "--runs",
        "3",
        "--run-id",
        run_id,
        "--output-dir",
        str(output_dir),
    ]
    result = subprocess.run(cmd, text=True, capture_output=True, env=env, check=True)

    assert "verification_state_reset_failed" not in result.stdout
    assert "JSONDecodeError" not in result.stdout
    assert "JSONDecodeError" not in result.stderr
    assert "[dry-run] docker compose run --rm -w /app pipeline python scripts/reset_city_verification_state.py --city fremont --since" in result.stderr

    rows = [json.loads(line) for line in (output_dir / run_id / "runs.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) == 3
    assert [row["verification_mode"] for row in rows] == ["first_time_onboarding"] * 3
    assert [row["state_reset_applied"] for row in rows] == [False, True, True]


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
if [[ "$*" == "compose config --images" ]]; then
  printf '%s\\n' 'town-council-crawler'
  exit 0
fi
if [[ "$1" == "image" && "$2" == "inspect" && "$3" == "town-council-crawler" ]]; then
  exit 0
fi
if [[ "$*" == *"scripts/reset_city_verification_state.py"* && "$*" == *"--print-baseline"* ]]; then
  printf '%s\\n' '{"city": "fremont", "baseline_event_count": 0, "baseline_max_record_date": null, "baseline_max_scraped_datetime": null}'
  exit 0
fi
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
        "3",
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
    assert row["verification_mode"] == "first_time_onboarding"
    assert row["state_reset_applied"] is False
    assert '"has_evidence": false' in result.stdout
    assert "stopping first-time verification for fremont after run 1" in result.stdout
    assert "run_pipeline.py" not in docker_log.read_text(encoding="utf-8")
    assert "segment_city_corpus.py" not in docker_log.read_text(encoding="utf-8")
    assert not curl_log.exists()


def test_onboarding_runner_resets_first_time_city_between_attempts(tmp_path):
    run_id = "first_time_resets"
    output_dir = tmp_path / "city_onboarding"
    output_dir.mkdir(parents=True, exist_ok=True)

    db_path = tmp_path / "first_time.sqlite"
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
if [[ "$*" == "compose config --images" ]]; then
  printf '%s\\n' 'town-council-crawler'
  exit 0
fi
if [[ "$1" == "image" && "$2" == "inspect" && "$3" == "town-council-crawler" ]]; then
  exit 0
fi
if [[ "$*" == *"scrapy crawl fremont"* ]]; then
  exit 0
fi
if [[ "$*" == *"scripts/check_city_crawl_evidence.py"* ]]; then
  printf '%s\\n' '{"city": "fremont", "event_stage_count": 3, "has_evidence": true, "url_stage_count": 2}'
  exit 0
fi
if [[ "$*" == *"scripts/reset_city_verification_state.py"* && "$*" == *"--print-baseline"* ]]; then
  printf '%s\\n' '{"city": "fremont", "baseline_event_count": 0, "baseline_max_record_date": null, "baseline_max_scraped_datetime": null}'
  exit 0
fi
if [[ "$*" == *"scripts/reset_city_verification_state.py"* ]]; then
  printf '%s\\n' '{"city": "fremont", "deleted_document_count": 1, "deleted_event_count": 1, "deleted_catalog_count": 1, "catalog_reference_count": 1, "deleted_data_issue_count": 0, "remaining_event_count": 0, "remaining_max_record_date": null, "remaining_max_scraped_datetime": null}'
  exit 0
fi
if [[ "$*" == *"run_pipeline.py"* ]]; then
  exit 0
fi
if [[ "$*" == *"scripts/segment_city_corpus.py --city fremont"* ]]; then
  exit 0
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
        "3",
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
    assert len(rows) == 3
    assert [row["verification_mode"] for row in rows] == ["first_time_onboarding"] * 3
    assert [row["state_reset_applied"] for row in rows] == [False, True, True]
    assert {row["overall_status"] for row in rows} == {"success"}
    docker_commands = docker_log.read_text(encoding="utf-8")
    assert docker_commands.count("scripts/reset_city_verification_state.py") == 3
    assert "--print-baseline" in docker_commands
    assert "--baseline-record-date" not in docker_commands
    assert "restoring first-time verification state for fremont before run 2" in result.stdout
    assert "restoring first-time verification state for fremont before run 3" in result.stdout
    baseline_payload = json.loads((output_dir / run_id / "baselines" / "fremont.json").read_text(encoding="utf-8"))
    assert baseline_payload["baseline_event_count"] == 0
    assert baseline_payload["baseline_max_record_date"] is None


def test_onboarding_runner_resets_anchor_aware_first_time_city_between_attempts(tmp_path):
    run_id = "anchor_reset"
    output_dir = tmp_path / "city_onboarding"
    output_dir.mkdir(parents=True, exist_ok=True)

    db_path = tmp_path / "anchor_reset.sqlite"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    with Session() as session:
        place = Place(
            name="San Leandro",
            state="CA",
            country="us",
            display_name="San Leandro, CA",
            ocd_division_id="ocd-division/country:us/state:ca/place:san_leandro",
        )
        session.add(place)
        session.flush()
        session.add(
            Event(
                ocd_id="baseline-event",
                ocd_division_id=place.ocd_division_id,
                place_id=place.id,
                scraped_datetime=datetime(2026, 3, 1, 12, 0, 0),
                record_date=date(2026, 3, 1),
                source="san_leandro",
                source_url="https://example.com/baseline",
                name="Baseline meeting",
            )
        )
        session.commit()
    engine.dispose()

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    docker_log = tmp_path / "docker.log"
    curl_log = tmp_path / "curl.log"
    crawl_log = tmp_path / "crawl.log"

    docker_stub = """#!/usr/bin/env bash
set -euo pipefail
printf '%s\\n' "$*" >> "$DOCKER_LOG"
if [[ "$*" == "compose config --images" ]]; then
  printf '%s\\n' 'town-council-crawler'
  exit 0
fi
if [[ "$1" == "image" && "$2" == "inspect" && "$3" == "town-council-crawler" ]]; then
  exit 0
fi
if [[ "$*" == *"scripts/reset_city_verification_state.py"* && "$*" == *"--print-baseline"* ]]; then
  printf '%s\\n' '{"city": "san_leandro", "baseline_event_count": 1, "baseline_max_record_date": "2026-03-01", "baseline_max_scraped_datetime": "2026-03-01T12:00:00Z"}'
  exit 0
fi
if [[ "$*" == *"scripts/reset_city_verification_state.py"* ]]; then
  printf '%s\\n' '{"city": "san_leandro", "deleted_document_count": 1, "deleted_event_count": 1, "deleted_catalog_count": 1, "catalog_reference_count": 1, "deleted_data_issue_count": 0, "remaining_event_count": 1, "remaining_max_record_date": "2026-03-01", "remaining_max_scraped_datetime": "2026-03-01T12:00:00Z"}'
  exit 0
fi
if [[ "$*" == *"scrapy crawl san_leandro"* ]]; then
  printf '%s\\n' "crawl" >> "$CRAWL_LOG"
  touch "$CRAWL_STATE"
  exit 0
fi
if [[ "$*" == *"scripts/check_city_crawl_evidence.py"* ]]; then
  if [[ -f "$CRAWL_STATE" ]]; then
    printf '%s\\n' '{"city": "san_leandro", "event_stage_count": 3, "has_evidence": true, "url_stage_count": 2}'
  else
    printf '%s\\n' '{"city": "san_leandro", "event_stage_count": 0, "has_evidence": false, "url_stage_count": 0}'
  fi
  exit 0
fi
if [[ "$*" == *"run_pipeline.py"* ]]; then
  exit 0
fi
if [[ "$*" == *"scripts/segment_city_corpus.py --city san_leandro"* ]]; then
  exit 0
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
    env["CRAWL_LOG"] = str(crawl_log)
    env["CRAWL_STATE"] = str(tmp_path / "crawl_state")
    env["PATH"] = f"{bin_dir}:{env['PATH']}"

    cmd = [
        "bash",
        "scripts/onboard_city_wave.sh",
        "wave1",
        "--cities",
        "san_leandro",
        "--runs",
        "3",
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
    assert len(rows) == 3
    assert [row["crawler_status"] for row in rows] == ["success", "success", "success"]
    assert [row["state_reset_applied"] for row in rows] == [False, True, True]
    docker_commands = docker_log.read_text(encoding="utf-8")
    assert docker_commands.count("--print-baseline") == 1
    assert docker_commands.count("--baseline-record-date 2026-03-01") == 2
    assert "restoring first-time verification state for san_leandro before run 2" in result.stdout
    assert "restoring first-time verification state for san_leandro before run 3" in result.stdout


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
if [[ \"$*\" == \"compose config --images\" ]]; then
  printf '%s\\n' 'town-council-crawler'
  exit 0
fi
if [[ \"$1\" == \"image\" && \"$2\" == \"inspect\" && \"$3\" == \"town-council-crawler\" ]]; then
  exit 0
fi
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
    assert row["verification_mode"] == "confirmation"
    assert row["state_reset_applied"] is False
    assert "stable delta no-op confirmation for hayward" in result.stdout
    assert "run_pipeline.py" not in docker_log.read_text(encoding="utf-8")
    assert "segment_city_corpus.py" not in docker_log.read_text(encoding="utf-8")

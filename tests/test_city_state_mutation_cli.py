from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine

from pipeline.models import Base


ROOT = Path(__file__).resolve().parents[1]
FLUSH_SCRIPT = ROOT / "scripts/flush_city_pipeline_state.py"
RESET_SCRIPT = ROOT / "scripts/reset_city_verification_state.py"


def _create_empty_database(database_path: Path) -> None:
    engine = create_engine(f"sqlite:///{database_path}")
    Base.metadata.create_all(engine)
    engine.dispose()


def _run_city_state_command(
    script_path: Path,
    arguments: list[str],
    database_path: Path,
) -> dict[str, int | str | bool | None]:
    environment = os.environ.copy()
    environment["DATABASE_URL"] = f"sqlite:///{database_path}"
    environment["PYTHONPATH"] = str(ROOT)
    completed = subprocess.run(
        [sys.executable, str(script_path), *arguments],
        cwd=ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)


def test_city_state_clis_preserve_distinct_defaults_and_json_contracts(tmp_path: Path) -> None:
    database_path = tmp_path / "city_state_cli.sqlite"
    _create_empty_database(database_path)

    flush_summary = _run_city_state_command(
        FLUSH_SCRIPT,
        ["--city", "fremont"],
        database_path,
    )
    reset_summary = _run_city_state_command(
        RESET_SCRIPT,
        ["--city", "fremont", "--since", "2026-03-15T13:21:09Z"],
        database_path,
    )

    assert flush_summary == {
        "catalog_reference_count": 0,
        "city": "fremont",
        "deleted_catalog_count": 0,
        "deleted_data_issue_count": 0,
        "deleted_document_count": 0,
        "deleted_event_count": 0,
        "deleted_event_stage_count": 0,
        "deleted_url_stage_count": 0,
        "deleted_url_stage_hist_count": 0,
        "dry_run": True,
        "remaining_catalog_count": 0,
        "remaining_document_count": 0,
        "remaining_event_count": 0,
        "remaining_event_stage_count": 0,
        "remaining_url_stage_count": 0,
        "remaining_url_stage_hist_count": 0,
    }
    assert reset_summary == {
        "baseline_record_date": None,
        "catalog_reference_count": 0,
        "city": "fremont",
        "deleted_catalog_count": 0,
        "deleted_data_issue_count": 0,
        "deleted_document_count": 0,
        "deleted_event_count": 0,
        "dry_run": False,
        "remaining_event_count": 0,
        "remaining_max_record_date": None,
        "remaining_max_scraped_datetime": None,
        "since": "2026-03-15T13:21:09Z",
    }

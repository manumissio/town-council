import importlib.util
import json
import sys
from pathlib import Path

from sqlalchemy.orm import sessionmaker

from pipeline import task_runtime


spec = importlib.util.spec_from_file_location(
    "backfill_summaries",
    Path("scripts/backfill_summaries.py"),
)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def _use_test_database(mocker, shared_engine) -> None:
    test_session = sessionmaker(bind=shared_engine)
    mocker.patch.object(task_runtime, "task_session", side_effect=test_session)


def test_backfill_summaries_json_mode_preserves_stdout_and_records_run_status(
    mocker,
    capsys,
    shared_engine,
    tmp_path: Path,
):
    _use_test_database(mocker, shared_engine)
    mocker.patch.object(
        sys,
        "argv",
        [
            "backfill_summaries.py",
            "--city",
            "sunnyvale",
            "--json",
            "--progress-every",
            "5",
            "--run-id",
            "summary_run",
            "--output-dir",
            str(tmp_path),
        ],
    )

    exit_code = mod.main()

    payload = json.loads(capsys.readouterr().out)
    run_dir = tmp_path / "backfill_summaries" / "summary_run"
    heartbeat = json.loads((run_dir / "heartbeat.json").read_text(encoding="utf-8"))
    events = [
        json.loads(event_line)
        for event_line in (run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert exit_code == 0
    assert payload["selected"] == 0
    assert payload["complete"] == 0
    assert heartbeat["status"] == "completed"
    assert events[-1]["event_type"] == "completed"


def test_backfill_summaries_human_mode_prints_run_location(
    mocker,
    capsys,
    shared_engine,
    tmp_path: Path,
):
    _use_test_database(mocker, shared_engine)
    mocker.patch.object(
        sys,
        "argv",
        [
            "backfill_summaries.py",
            "--city",
            "sunnyvale",
            "--run-id",
            "human_run",
            "--output-dir",
            str(tmp_path),
        ],
    )

    exit_code = mod.main()

    captured = capsys.readouterr()
    assert exit_code == 0
    assert f"[summary_backfill] run_status run_id=human_run artifact_dir={tmp_path}/backfill_summaries/human_run" in captured.out
    assert "run_id: human_run" in captured.out
    assert "selected: 0" in captured.out

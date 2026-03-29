from __future__ import annotations

import json
from pathlib import Path

import pytest

from pipeline.maintenance_run_status import MaintenanceRunStatus, validate_run_id


def test_validate_run_id_rejects_unsafe_values():
    with pytest.raises(ValueError):
        validate_run_id("../bad")
    with pytest.raises(ValueError):
        validate_run_id("bad/name")


def test_maintenance_run_status_writes_manifest_heartbeat_events_and_result(tmp_path: Path):
    tracker = MaintenanceRunStatus(
        tool_name="backfill_summaries",
        output_dir=str(tmp_path),
        run_id="run_123",
        metadata={"city": "sunnyvale"},
    )

    tracker.heartbeat(status="running", stage="summary", counts={"selected": 5}, progress={"done": 1, "total": 5})
    tracker.event(event_type="stage_start", stage="summary", counts={"selected": 5})
    tracker.event(
        event_type="progress",
        stage="summary",
        counts={"selected": 5, "complete": 1},
        last_catalog_id=1001,
        detail={"done": 1, "total": 5},
    )
    tracker.result(status="completed", counts={"complete": 5}, elapsed_seconds=12.34)

    run_dir = tmp_path / "backfill_summaries" / "run_123"
    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    heartbeat = json.loads((run_dir / "heartbeat.json").read_text(encoding="utf-8"))
    result = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
    events = [json.loads(line) for line in (run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()]

    assert manifest["tool"] == "backfill_summaries"
    assert manifest["run_id"] == "run_123"
    assert manifest["metadata"]["city"] == "sunnyvale"
    assert heartbeat["status"] == "running"
    assert heartbeat["stage"] == "summary"
    assert heartbeat["counts"]["selected"] == 5
    assert heartbeat["progress"] == {"done": 1, "total": 5}
    assert result["status"] == "completed"
    assert result["counts"]["complete"] == 5
    assert events[0]["event_type"] == "stage_start"
    assert events[1]["last_catalog_id"] == 1001


def test_maintenance_run_status_rejects_existing_run_dir(tmp_path: Path):
    MaintenanceRunStatus(
        tool_name="backfill_summaries",
        output_dir=str(tmp_path),
        run_id="run_123",
        metadata={},
    )
    with pytest.raises(ValueError, match="run directory already exists"):
        MaintenanceRunStatus(
            tool_name="backfill_summaries",
            output_dir=str(tmp_path),
            run_id="run_123",
            metadata={},
        )


def test_maintenance_run_status_resolves_relative_output_dir_under_repo_root():
    tracker = MaintenanceRunStatus(
        tool_name="backfill_summaries",
        output_dir="tmp/maintenance_status_test",
        run_id="relative_run",
        metadata={},
    )
    try:
        assert tracker.paths.run_dir.is_absolute()
        assert str(tracker.paths.run_dir).endswith("tmp/maintenance_status_test/backfill_summaries/relative_run")
    finally:
        if tracker.paths.run_dir.exists():
            for path in sorted(tracker.paths.run_dir.glob("**/*"), reverse=True):
                if path.is_file():
                    path.unlink()
                elif path.is_dir():
                    path.rmdir()
            tracker.paths.run_dir.rmdir()

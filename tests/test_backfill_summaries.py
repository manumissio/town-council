import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace


spec = importlib.util.spec_from_file_location(
    "backfill_summaries",
    Path("scripts/backfill_summaries.py"),
)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


class _FakeRunStatus:
    def __init__(self, *, tool_name, output_dir, run_id, metadata):
        self.tool_name = tool_name
        self.run_id = run_id or "summary_run"
        self.metadata = metadata
        self.paths = SimpleNamespace(run_dir=Path(output_dir) / tool_name / self.run_id)
        self.events = []
        self.heartbeats = []
        self.results = []

    def heartbeat(self, **payload):
        self.heartbeats.append(payload)

    def event(self, **payload):
        self.events.append(payload)

    def result(self, **payload):
        self.results.append(payload)


def test_backfill_summaries_json_mode_preserves_stdout_and_records_run_status(mocker, capsys):
    fake_run = _FakeRunStatus(
        tool_name="backfill_summaries",
        output_dir="experiments/results/maintenance",
        run_id="summary_run",
        metadata={},
    )
    mocker.patch.object(mod, "MaintenanceRunStatus", return_value=fake_run)

    def _fake_backfill(**kwargs):
        kwargs["progress_callback"](
            {
                "event_type": "stage_start",
                "stage": "summary",
                "counts": {"selected": 2},
                "detail": {"selected": 2},
            }
        )
        kwargs["progress_callback"](
            {
                "event_type": "progress",
                "stage": "summary",
                "counts": {"selected": 2, "complete": 1},
                "last_catalog_id": 9001,
                "detail": {"done": 1, "total": 2, "last_status": "complete"},
            }
        )
        kwargs["progress_callback"](
            {
                "event_type": "stage_finish",
                "stage": "summary",
                "counts": {"selected": 2, "complete": 2},
            }
        )
        return {"selected": 2, "complete": 2, "cached": 0, "stale": 0, "blocked_low_signal": 0, "blocked_ungrounded": 0, "not_generated_yet": 0, "error": 0, "other": 0, "llm_complete": 2, "deterministic_fallback_complete": 0}

    mocker.patch.object(mod, "run_summary_hydration_backfill", side_effect=_fake_backfill)
    mocker.patch.object(
        sys,
        "argv",
        ["backfill_summaries.py", "--city", "sunnyvale", "--json", "--progress-every", "5"],
    )

    exit_code = mod.main()

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["complete"] == 2
    assert fake_run.heartbeats[-1]["status"] == "completed"
    assert fake_run.events[-1]["event_type"] == "completed"


def test_backfill_summaries_human_mode_prints_run_location(mocker, capsys):
    fake_run = _FakeRunStatus(
        tool_name="backfill_summaries",
        output_dir="experiments/results/maintenance",
        run_id="human_run",
        metadata={},
    )
    mocker.patch.object(mod, "MaintenanceRunStatus", return_value=fake_run)
    mocker.patch.object(
        mod,
        "run_summary_hydration_backfill",
        return_value={"selected": 0, "complete": 0, "cached": 0, "stale": 0, "blocked_low_signal": 0, "blocked_ungrounded": 0, "not_generated_yet": 0, "error": 0, "other": 0, "llm_complete": 0, "deterministic_fallback_complete": 0},
    )
    mocker.patch.object(sys, "argv", ["backfill_summaries.py", "--city", "sunnyvale"])

    exit_code = mod.main()

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "[summary_backfill] run_status run_id=human_run artifact_dir=experiments/results/maintenance/backfill_summaries/human_run" in captured.out
    assert "run_id: human_run" in captured.out

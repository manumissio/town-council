import json
from pathlib import Path

from pipeline import profiling


def test_profile_span_writes_jsonl_event(monkeypatch, tmp_path: Path):
    monkeypatch.setenv(profiling.PROFILE_RUN_ID_ENV, "profile_run")
    monkeypatch.setenv(profiling.PROFILE_MODE_ENV, "triage")
    monkeypatch.setenv(profiling.PROFILE_ARTIFACT_DIR_ENV, str(tmp_path))
    monkeypatch.setenv(profiling.PROFILE_BASELINE_VALID_ENV, "0")

    with profiling.profile_span(phase="download", component="subprocess", metadata={"command": ["python", "downloader.py"]}):
        pass

    rows = [json.loads(line) for line in (tmp_path / "spans.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1
    assert rows[0]["run_id"] == "profile_run"
    assert rows[0]["phase"] == "download"
    assert rows[0]["component"] == "subprocess"
    assert rows[0]["event_type"] == "span"

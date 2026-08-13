import json
from pathlib import Path

import pytest

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


def test_profile_span_excludes_nested_observer_work(monkeypatch, tmp_path: Path):
    monkeypatch.setenv(profiling.PROFILE_RUN_ID_ENV, "profile_run")
    monkeypatch.setenv(profiling.PROFILE_ARTIFACT_DIR_ENV, str(tmp_path))
    clock = [0.0]
    monkeypatch.setattr(profiling.time, "perf_counter", lambda: clock[0])

    with profiling.profile_span(phase="pipeline_total", component="pipeline"):
        clock[0] += 2.0
        with profiling.profile_observer():
            clock[0] += 3.0
        clock[0] += 5.0

    row = json.loads((tmp_path / "spans.jsonl").read_text(encoding="utf-8"))
    assert row["duration_s"] == 7.0
    assert row["metadata"]["observer_overhead_s"] == 3.0


def test_workload_duration_excludes_observer_work(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(profiling.time, "perf_counter", lambda: clock[0])
    started_perf = profiling.time.perf_counter()
    observer_at_start = profiling.observer_seconds()

    clock[0] += 2.0
    with profiling.profile_observer():
        clock[0] += 3.0
    clock[0] += 5.0

    assert profiling.workload_duration_seconds(started_perf, observer_at_start) == 7.0


def test_failed_span_excludes_observer_work(monkeypatch, tmp_path: Path):
    monkeypatch.setenv(profiling.PROFILE_RUN_ID_ENV, "profile_run")
    monkeypatch.setenv(profiling.PROFILE_ARTIFACT_DIR_ENV, str(tmp_path))
    clock = [0.0]
    monkeypatch.setattr(profiling.time, "perf_counter", lambda: clock[0])

    with pytest.raises(RuntimeError, match="profiled work failed"):
        with profiling.profile_span(phase="pipeline_total", component="pipeline"):
            clock[0] += 4.0
            with profiling.profile_observer():
                clock[0] += 3.0
            raise RuntimeError("profiled work failed")

    recorded_span = json.loads((tmp_path / "spans.jsonl").read_text(encoding="utf-8"))
    assert recorded_span["outcome"] == "failure"
    assert recorded_span["duration_s"] == 4.0
    assert recorded_span["metadata"]["observer_overhead_s"] == 3.0


def test_phase_eligibility_writes_normalized_catalog_ids(monkeypatch, tmp_path: Path):
    monkeypatch.setenv(profiling.PROFILE_RUN_ID_ENV, "profile_run")
    monkeypatch.setenv(profiling.PROFILE_MODE_ENV, "baseline")
    monkeypatch.setenv(profiling.PROFILE_ARTIFACT_DIR_ENV, str(tmp_path))
    monkeypatch.setenv(profiling.PROFILE_BASELINE_VALID_ENV, "0")

    profiling.append_phase_eligibility(
        phase="summarize",
        boundary="before",
        subject="catalog",
        eligible_ids=[13, 11, 13, 12],
    )

    rows = [json.loads(line) for line in (tmp_path / "spans.jsonl").read_text(encoding="utf-8").splitlines()]
    assert rows == [
        {
            "baseline_valid": False,
            "boundary": "before",
            "eligible_count": 3,
            "eligible_ids": [11, 12, 13],
            "event_type": "phase_eligibility",
            "mode": "baseline",
            "phase": "summarize",
            "run_id": "profile_run",
            "subject": "catalog",
            "timestamp": rows[0]["timestamp"],
        }
    ]


@pytest.mark.parametrize("subject", ["place", "event"])
def test_phase_eligibility_preserves_non_catalog_subjects(monkeypatch, tmp_path: Path, subject: str):
    monkeypatch.setenv(profiling.PROFILE_RUN_ID_ENV, "profile_run")
    monkeypatch.setenv(profiling.PROFILE_ARTIFACT_DIR_ENV, str(tmp_path))

    profiling.append_phase_eligibility(
        phase="org_backfill",
        boundary="before",
        subject=subject,
        eligible_ids=[3, 2, 3],
    )

    row = json.loads((tmp_path / "spans.jsonl").read_text(encoding="utf-8"))
    assert row["subject"] == subject
    assert row["eligible_ids"] == [2, 3]


def test_selected_catalog_ids_accept_comments_and_duplicates(monkeypatch, tmp_path: Path):
    manifest_path = tmp_path / "selected_catalogs.txt"
    manifest_path.write_text("11\n12 # retained\n11\n", encoding="utf-8")
    monkeypatch.setenv(profiling.PROFILE_CATALOG_MANIFEST_ENV, str(manifest_path))

    assert profiling.selected_catalog_ids() == {11, 12}


def test_selected_catalog_ids_leave_scope_unset_without_manifest(monkeypatch):
    monkeypatch.delenv(profiling.PROFILE_CATALOG_MANIFEST_ENV, raising=False)

    assert profiling.selected_catalog_ids() is None


@pytest.mark.parametrize("manifest_text", ["", "not-a-catalog-id\n"])
def test_selected_catalog_ids_reject_empty_or_malformed_manifest(monkeypatch, tmp_path: Path, manifest_text: str):
    manifest_path = tmp_path / "invalid_manifest.txt"
    manifest_path.write_text(manifest_text, encoding="utf-8")
    monkeypatch.setenv(profiling.PROFILE_CATALOG_MANIFEST_ENV, str(manifest_path))

    with pytest.raises(ValueError):
        profiling.selected_catalog_ids()


def test_selected_catalog_ids_reject_missing_manifest(monkeypatch, tmp_path: Path):
    missing_manifest = tmp_path / "missing_manifest.txt"
    monkeypatch.setenv(profiling.PROFILE_CATALOG_MANIFEST_ENV, str(missing_manifest))

    with pytest.raises(FileNotFoundError):
        profiling.selected_catalog_ids()

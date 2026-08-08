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

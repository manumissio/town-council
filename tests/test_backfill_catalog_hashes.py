import importlib
from pathlib import Path

import pytest

from pipeline.models import Catalog


def test_backfill_limit_zero_does_not_process_all_rows(db_session):
    module = importlib.import_module("pipeline.backfill_catalog_hashes")

    db_session.add_all(
        [
            Catalog(filename="a.pdf", url_hash="limit-zero-a", content="Agenda A"),
            Catalog(filename="b.pdf", url_hash="limit-zero-b", content="Agenda B"),
        ]
    )
    db_session.commit()

    counts = module.backfill(limit=0)

    assert counts["updated"] == 0
    assert counts["skipped"] == 0
    refreshed = db_session.query(Catalog).filter(Catalog.url_hash.in_(["limit-zero-a", "limit-zero-b"])).all()
    assert all(row.content_hash is None for row in refreshed)


def test_backfill_updates_only_manifest_selected_catalogs(monkeypatch, tmp_path: Path, db_session):
    module = importlib.import_module("pipeline.backfill_catalog_hashes")
    selected = Catalog(filename="selected.pdf", url_hash="scope-selected", content="Selected agenda")
    excluded = Catalog(filename="excluded.pdf", url_hash="scope-excluded", content="Excluded agenda")
    db_session.add_all([selected, excluded])
    db_session.commit()
    manifest_path = tmp_path / "selected_catalogs.txt"
    manifest_path.write_text(f"{selected.id}\n", encoding="utf-8")
    monkeypatch.setenv("TC_PROFILE_CATALOG_MANIFEST", str(manifest_path))

    counts = module.backfill()

    db_session.refresh(selected)
    db_session.refresh(excluded)
    assert counts["updated"] == 1
    assert selected.content_hash is not None
    assert excluded.content_hash is None


@pytest.mark.parametrize("manifest_text", [None, "", "invalid\n"])
def test_backfill_rejects_invalid_manifest_without_mutation(
    monkeypatch,
    tmp_path: Path,
    db_session,
    manifest_text: str | None,
):
    module = importlib.import_module("pipeline.backfill_catalog_hashes")
    catalog = Catalog(filename="untouched.pdf", url_hash=f"invalid-scope-{manifest_text!r}", content="Agenda")
    db_session.add(catalog)
    db_session.commit()
    manifest_path = tmp_path / "invalid_manifest.txt"
    if manifest_text is not None:
        manifest_path.write_text(manifest_text, encoding="utf-8")
    monkeypatch.setenv("TC_PROFILE_CATALOG_MANIFEST", str(manifest_path))

    expected_error = FileNotFoundError if manifest_text is None else ValueError
    with pytest.raises(expected_error):
        module.backfill()

    db_session.refresh(catalog)
    assert catalog.content_hash is None

import importlib
from pathlib import Path

import pytest

from pipeline.content_hash import compute_content_hash
from pipeline.models import AgendaItem, Catalog, Document, Event, Place
from pipeline.summary_freshness import compute_agenda_items_hash


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


def test_normalize_catalog_hashes_does_not_count_unchanged_whitespace_content(db_session) -> None:
    module = importlib.import_module("pipeline.backfill_catalog_hashes")
    catalog = Catalog(filename="whitespace.pdf", url_hash="whitespace-content", content="   ")
    db_session.add(catalog)
    db_session.flush()

    counts = module.normalize_catalog_hashes(db_session, catalog_ids=[catalog.id])

    assert counts == {"updated": 0, "skipped": 0}
    assert catalog.content_hash is None


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


def test_normalize_catalog_hashes_uses_replay_candidate_agenda_order(db_session) -> None:
    module = importlib.import_module("pipeline.backfill_catalog_hashes")
    place = Place(name="Hash order", state="CA", ocd_division_id="ocd-division/hash-order")
    db_session.add(place)
    db_session.flush()
    event = Event(name="Hash order meeting", place_id=place.id)
    db_session.add(event)
    db_session.flush()
    catalog = Catalog(
        filename="hash-order.pdf",
        url_hash="hash-order",
        content="Agenda",
        agenda_segmentation_status="complete",
        agenda_items_hash="stale-agenda-hash",
    )
    unselected_catalog = Catalog(
        filename="hash-order-unselected.pdf",
        url_hash="hash-order-unselected",
        content="Unselected agenda",
    )
    db_session.add_all([catalog, unselected_catalog])
    db_session.flush()
    db_session.add(Document(catalog_id=catalog.id, event_id=event.id, place_id=place.id, category="agenda"))
    db_session.add_all(
        [
            AgendaItem(catalog_id=catalog.id, event_id=event.id, order=1, title="First inserted"),
            AgendaItem(catalog_id=catalog.id, event_id=event.id, order=1, title="Second inserted"),
        ]
    )
    db_session.flush()
    catalog_id = catalog.id

    module.normalize_catalog_hashes(db_session, catalog_ids=[catalog_id])

    ordered_items = (
        db_session.query(AgendaItem).filter_by(catalog_id=catalog_id).order_by(AgendaItem.order, AgendaItem.id).all()
    )
    assert catalog.agenda_items_hash == compute_agenda_items_hash(ordered_items)
    assert unselected_catalog.content_hash is None


def test_normalize_catalog_hashes_repairs_explicit_empty_hashes_by_default(db_session) -> None:
    module = importlib.import_module("pipeline.backfill_catalog_hashes")
    catalog = Catalog(
        filename="empty-hashes.pdf",
        url_hash="empty-hashes",
        content="Minutes",
        content_hash="",
        summary="Existing summary",
        summary_source_hash="",
        topics=[],
        topics_source_hash="",
        entities={},
        entities_source_hash="",
    )
    db_session.add(catalog)
    db_session.flush()

    module.normalize_catalog_hashes(db_session, catalog_ids=[catalog.id])

    expected_hash = compute_content_hash("Minutes")
    assert catalog.content_hash == expected_hash
    assert catalog.summary_source_hash == expected_hash
    assert catalog.topics_source_hash == expected_hash
    assert catalog.entities_source_hash == expected_hash


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

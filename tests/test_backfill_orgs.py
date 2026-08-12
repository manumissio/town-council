from contextlib import contextmanager
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from pipeline import backfill_orgs, profiling
from pipeline.backfill_orgs import backfill_organizations
from pipeline.models import Base, Event, Organization, Place, Catalog, Document


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine)()


def _eligibility_rows(artifact_dir: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in (artifact_dir / "spans.jsonl").read_text(encoding="utf-8").splitlines()
    ]


def _add_event_document(
    session,
    place: Place,
    *,
    meeting_type: str,
    suffix: str,
) -> tuple[Event, Catalog]:
    event = Event(name=suffix, place_id=place.id, meeting_type=meeting_type)
    session.add(event)
    session.flush()
    catalog = Catalog(url_hash=f"hash-{suffix}", location=f"/tmp/{suffix}.pdf")
    session.add(catalog)
    session.flush()
    session.add(
        Document(
            event_id=event.id,
            place_id=place.id,
            catalog_id=catalog.id,
            url=f"https://example.com/{suffix}",
        )
    )
    return event, catalog


def _patch_reindex_runtime(mocker, engine) -> None:
    @contextmanager
    def test_db_session():
        session = sessionmaker(bind=engine)()
        try:
            yield session
        finally:
            session.close()

    search_index = MagicMock()
    search_index.delete_documents.return_value = SimpleNamespace(task_uid=1)
    search_client = MagicMock()
    search_client.create_index.return_value = SimpleNamespace(task_uid=2)
    search_client.index.return_value = search_index
    search_client.wait_for_task.return_value = SimpleNamespace(status="succeeded", error=None)
    mocker.patch("pipeline.indexer.db_session", test_db_session)
    mocker.patch("pipeline.indexer.meilisearch.Client", return_value=search_client)


def test_backfill_creates_default_and_links_events(mocker):
    engine, session = _session()
    place = Place(name="Test City", state="CA", ocd_division_id="ocd-division/country:us/state:ca/place:test")
    session.add(place)
    session.flush()
    session.add_all(
        [
            Event(name="Regular", place_id=place.id, meeting_type="Regular City Council"),
            Event(name="Planning", place_id=place.id, meeting_type="Planning Commission"),
        ]
    )
    session.flush()
    events = session.query(Event).order_by(Event.id.asc()).all()
    for idx, event in enumerate(events, start=1):
        catalog = Catalog(url_hash=f"h{idx}", location=f"/tmp/{idx}.pdf", content="Meeting content")
        session.add(catalog)
        session.flush()
        session.add(Document(event_id=event.id, place_id=place.id, catalog_id=catalog.id, url=f"https://example.com/{idx}"))
    session.commit()
    session.close()

    mocker.patch("pipeline.backfill_orgs.db_connect", return_value=engine)
    _patch_reindex_runtime(mocker, engine)

    counts = backfill_organizations()

    verify = sessionmaker(bind=engine)()
    org_names = {o.name for o in verify.query(Organization).all()}
    assert "City Council" in org_names
    assert "Planning Commission" in org_names
    assert verify.query(Event).filter(Event.organization_id.is_(None)).count() == 0
    assert counts["reindexed"] == 2
    assert counts["failed_reindex"] == 0
    verify.close()
    engine.dispose()


def test_backfill_is_idempotent(mocker):
    engine, session = _session()
    place = Place(name="Test City", state="CA", ocd_division_id="ocd-division/country:us/state:ca/place:test")
    session.add(place)
    session.flush()
    place_id = place.id
    event = Event(name="Parks", place_id=place.id, meeting_type="Parks Committee")
    session.add(event)
    session.flush()
    catalog = Catalog(url_hash="parks-hash", location="/tmp/parks.pdf", content="Parks meeting")
    session.add(catalog)
    session.flush()
    session.add(Document(event_id=event.id, place_id=place.id, catalog_id=catalog.id, url="https://example.com/parks"))
    session.commit()
    session.close()

    mocker.patch("pipeline.backfill_orgs.db_connect", return_value=engine)
    _patch_reindex_runtime(mocker, engine)

    first_counts = backfill_organizations()
    second_counts = backfill_organizations()

    verify = sessionmaker(bind=engine)()
    council_count = verify.query(Organization).filter_by(place_id=place_id, name="City Council").count()
    parks_count = verify.query(Organization).filter_by(place_id=place_id, name="Parks & Recreation Commission").count()
    assert council_count == 1
    assert parks_count == 1
    assert first_counts["reindexed"] == 1
    assert first_counts["failed_reindex"] == 0
    assert second_counts["reindexed"] == 0
    verify.close()
    engine.dispose()


def test_profiled_backfill_records_exact_place_and_event_obligations(
    monkeypatch,
    mocker,
    tmp_path: Path,
):
    engine, session = _session()
    place = Place(name="Test City", state="CA", ocd_division_id="ocd-division/test")
    session.add(place)
    session.flush()
    event = Event(name="Planning", place_id=place.id, meeting_type="Planning Commission")
    session.add(event)
    session.commit()
    place_id = int(place.id)
    event_id = int(event.id)
    session.close()

    monkeypatch.setenv(profiling.PROFILE_RUN_ID_ENV, "profile_run")
    monkeypatch.setenv(profiling.PROFILE_ARTIFACT_DIR_ENV, str(tmp_path))
    mocker.patch("pipeline.backfill_orgs.db_connect", return_value=engine)

    counts = backfill_organizations()

    assert [(row["subject"], row["boundary"], row["eligible_ids"]) for row in _eligibility_rows(tmp_path)] == [
        ("place", "before", [place_id]),
        ("event", "before", [event_id]),
        ("place", "after", []),
        ("event", "after", []),
    ]
    assert counts == {"selected": 1, "linked": 1, "reindexed": 0, "failed_reindex": 0}
    verify = sessionmaker(bind=engine)()
    assert verify.get(Event, event_id).organization.name == "Planning Commission"
    verify.close()
    engine.dispose()


def test_profiled_backfill_records_paired_empty_obligations(monkeypatch, mocker, tmp_path: Path):
    engine, session = _session()
    session.close()
    monkeypatch.setenv(profiling.PROFILE_RUN_ID_ENV, "profile_run")
    monkeypatch.setenv(profiling.PROFILE_ARTIFACT_DIR_ENV, str(tmp_path))
    mocker.patch("pipeline.backfill_orgs.db_connect", return_value=engine)

    counts = backfill_organizations()

    assert [(row["subject"], row["boundary"], row["eligible_ids"]) for row in _eligibility_rows(tmp_path)] == [
        ("place", "before", []),
        ("event", "before", []),
        ("place", "after", []),
        ("event", "after", []),
    ]
    assert counts["selected"] == 0
    engine.dispose()


def test_profiled_backfill_scopes_and_deduplicates_manifest_events(
    monkeypatch,
    mocker,
    tmp_path: Path,
):
    engine, session = _session()
    selected_place = Place(name="Selected", state="CA", ocd_division_id="ocd-division/selected")
    excluded_place = Place(name="Excluded", state="CA", ocd_division_id="ocd-division/excluded")
    session.add_all([selected_place, excluded_place])
    session.flush()
    selected_event, first_catalog = _add_event_document(
        session,
        selected_place,
        meeting_type="Planning Commission",
        suffix="selected-one",
    )
    planning_organization = Organization(
        name="Planning Commission",
        place_id=selected_place.id,
        ocd_id="ocd-org/selected-planning",
    )
    session.add(planning_organization)
    session.flush()
    selected_event.organization_id = planning_organization.id
    second_catalog = Catalog(url_hash="hash-selected-two", location="/tmp/selected-two.pdf")
    session.add(second_catalog)
    session.flush()
    session.add(
        Document(
            event_id=selected_event.id,
            place_id=selected_place.id,
            catalog_id=second_catalog.id,
            url="https://example.com/selected-two",
        )
    )
    _add_event_document(session, excluded_place, meeting_type="Regular", suffix="excluded")
    session.commit()
    selected_place_id = int(selected_place.id)
    manifest_path = tmp_path / "manifest.txt"
    manifest_path.write_text(f"{first_catalog.id}\n{second_catalog.id}\n", encoding="utf-8")
    session.close()

    monkeypatch.setenv(profiling.PROFILE_RUN_ID_ENV, "profile_run")
    monkeypatch.setenv(profiling.PROFILE_ARTIFACT_DIR_ENV, str(tmp_path))
    monkeypatch.setenv(profiling.PROFILE_CATALOG_MANIFEST_ENV, str(manifest_path))
    mocker.patch("pipeline.backfill_orgs.db_connect", return_value=engine)

    counts = backfill_organizations()

    before_rows = [row for row in _eligibility_rows(tmp_path) if row["boundary"] == "before"]
    assert [(row["subject"], row["eligible_ids"]) for row in before_rows] == [
        ("place", [selected_place_id]),
        ("event", []),
    ]
    assert counts["selected"] == 1
    engine.dispose()


@pytest.mark.parametrize("organization_name", ["City Council", "Planning Commission"])
def test_profiled_backfill_preserves_first_match_for_duplicate_targets(
    monkeypatch,
    mocker,
    tmp_path: Path,
    organization_name: str,
):
    engine, session = _session()
    place = Place(name="Test City", state="CA", ocd_division_id="ocd-division/test")
    session.add(place)
    session.flush()
    event = Event(name="Meeting", place_id=place.id, meeting_type=organization_name)
    session.add(event)
    session.add_all(
        [
            Organization(name=organization_name, place_id=place.id, ocd_id="ocd-org/one"),
            Organization(name=organization_name, place_id=place.id, ocd_id="ocd-org/two"),
        ]
    )
    session.commit()
    session.execute(text("PRAGMA reverse_unordered_selects = ON"))
    event_id = int(event.id)
    session.close()
    mocker.patch("pipeline.backfill_orgs.db_connect", return_value=engine)

    duplicate_session = sessionmaker(bind=engine)()
    duplicate_ids = {
        int(organization.id)
        for organization in duplicate_session.query(Organization).all()
        if organization.name == organization_name
    }
    duplicate_session.close()

    unprofiled_counts = backfill_organizations()
    reset_session = sessionmaker(bind=engine)()
    unprofiled_organization_id = int(reset_session.get(Event, event_id).organization_id)
    reset_session.get(Event, event_id).organization_id = None
    reset_session.commit()
    reset_session.close()

    monkeypatch.setenv(profiling.PROFILE_RUN_ID_ENV, "profile_run")
    monkeypatch.setenv(profiling.PROFILE_ARTIFACT_DIR_ENV, str(tmp_path))
    profiled_counts = backfill_organizations()

    verify = sessionmaker(bind=engine)()
    assert verify.get(Event, event_id).organization_id == min(duplicate_ids)
    assert unprofiled_organization_id == min(duplicate_ids)
    assert verify.query(Organization).filter_by(name=organization_name).count() == 2
    assert unprofiled_counts["linked"] == 1
    assert profiled_counts["linked"] == 1
    assert [
        (row["subject"], row["boundary"], row["eligible_ids"])
        for row in _eligibility_rows(tmp_path)
    ] == [
        ("place", "before", []),
        ("event", "before", [event_id]),
        ("place", "after", []),
        ("event", "after", []),
    ]
    verify.close()
    engine.dispose()


def test_unprofiled_backfill_preserves_first_match_for_duplicate_targets(mocker):
    engine, session = _session()
    place = Place(name="Test City", state="CA", ocd_division_id="ocd-division/test")
    session.add(place)
    session.flush()
    organizations = [
        Organization(name="City Council", place_id=place.id, ocd_id="ocd-org/one"),
        Organization(name="City Council", place_id=place.id, ocd_id="ocd-org/two"),
    ]
    session.add_all(organizations)
    session.flush()
    event = Event(name="Meeting", place_id=place.id, meeting_type="Regular")
    session.add(event)
    session.commit()
    event_id = int(event.id)
    organization_ids = {int(organization.id) for organization in organizations}
    session.close()
    mocker.patch("pipeline.backfill_orgs.db_connect", return_value=engine)

    backfill_organizations()

    verify = sessionmaker(bind=engine)()
    assert verify.get(Event, event_id).organization_id in organization_ids
    verify.close()
    engine.dispose()


def test_profiled_backfill_records_after_state_when_reindex_fails(
    monkeypatch,
    mocker,
    tmp_path: Path,
):
    engine, session = _session()
    place = Place(name="Test City", state="CA", ocd_division_id="ocd-division/test")
    session.add(place)
    session.flush()
    event, _catalog = _add_event_document(session, place, meeting_type="Regular", suffix="regular")
    session.commit()
    place_id = int(place.id)
    event_id = int(event.id)
    session.close()
    monkeypatch.setenv(profiling.PROFILE_RUN_ID_ENV, "profile_run")
    monkeypatch.setenv(profiling.PROFILE_ARTIFACT_DIR_ENV, str(tmp_path))
    mocker.patch("pipeline.backfill_orgs.db_connect", return_value=engine)
    mocker.patch("pipeline.indexer.meilisearch.Client", side_effect=RuntimeError("search unavailable"))

    counts = backfill_organizations()

    assert counts["failed_reindex"] == 1
    assert [(row["boundary"], row["eligible_ids"]) for row in _eligibility_rows(tmp_path)] == [
        ("before", [place_id]),
        ("before", [event_id]),
        ("after", []),
        ("after", []),
    ]
    verify = sessionmaker(bind=engine)()
    assert verify.get(Event, event_id).organization_id is not None
    verify.close()
    engine.dispose()


def test_profiled_backfill_omits_after_rows_when_database_work_fails(
    monkeypatch,
    mocker,
    tmp_path: Path,
):
    engine, session = _session()
    place = Place(name="Test City", state="CA", ocd_division_id="ocd-division/test")
    session.add(place)
    session.commit()
    session.execute(
        text(
            "CREATE TRIGGER reject_organization_insert BEFORE INSERT ON organization "
            "BEGIN SELECT RAISE(FAIL, 'organization insert rejected'); END"
        )
    )
    session.commit()
    session.close()
    monkeypatch.setenv(profiling.PROFILE_RUN_ID_ENV, "profile_run")
    monkeypatch.setenv(profiling.PROFILE_ARTIFACT_DIR_ENV, str(tmp_path))
    mocker.patch("pipeline.backfill_orgs.db_connect", return_value=engine)

    with pytest.raises(SQLAlchemyError, match="organization insert rejected"):
        backfill_organizations()

    assert [(row["subject"], row["boundary"]) for row in _eligibility_rows(tmp_path)] == [
        ("place", "before"),
        ("event", "before"),
    ]
    verify = sessionmaker(bind=engine)()
    assert verify.query(Organization).count() == 0
    verify.close()
    engine.dispose()

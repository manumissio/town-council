from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

import pipeline.db_session as db_session_module
from pipeline.models import Base, Catalog, DataIssue, Document, Event, EventStage, Place, UrlStage, UrlStageHist
from scripts.reset_city_verification_state import reset_city_verification_state


def _load_rewind_module():
    spec = importlib.util.spec_from_file_location(
        "rewind_pending_city_onboarding", Path("scripts/rewind_pending_city_onboarding.py")
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _setup_city_graph(db_path: Path, monkeypatch) -> sessionmaker:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    db_session_module._SessionLocal = None
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def test_reset_city_verification_state_dry_run_preserves_rows(tmp_path, monkeypatch):
    Session = _setup_city_graph(tmp_path / "dry_run.sqlite", monkeypatch)
    now = datetime.now(UTC).replace(tzinfo=None, microsecond=0)

    with Session() as session:
        place = Place(
            name="Fremont",
            state="CA",
            country="us",
            display_name="Fremont, CA",
            ocd_division_id="ocd-division/country:us/state:ca/place:fremont",
        )
        session.add(place)
        session.flush()

        event = Event(
            ocd_id="new-event",
            ocd_division_id=place.ocd_division_id,
            place_id=place.id,
            scraped_datetime=now + timedelta(minutes=1),
            record_date=date(2026, 2, 1),
            source="fremont",
            source_url="https://example.com/new",
            name="New meeting",
        )
        session.add(event)
        session.flush()

        catalog = Catalog(url_hash="new", location="/tmp/new.pdf")
        session.add(catalog)
        session.flush()
        session.add(Document(place_id=place.id, event_id=event.id, catalog_id=catalog.id, url_hash="new"))
        session.commit()

    result = reset_city_verification_state("fremont", now.strftime("%Y-%m-%dT%H:%M:%SZ"), dry_run=True)

    assert result["dry_run"] is True
    assert result["deleted_event_count"] == 1
    assert result["deleted_document_count"] == 1
    assert result["deleted_catalog_count"] == 1

    with Session() as session:
        assert session.query(Event).count() == 1
        assert session.query(Document).count() == 1
        assert session.query(Catalog).count() == 1


def test_reset_city_verification_state_deletes_only_events_in_window_and_unreferenced_catalogs(tmp_path, monkeypatch):
    Session = _setup_city_graph(tmp_path / "reset_city.sqlite", monkeypatch)
    now = datetime.now(UTC).replace(tzinfo=None, microsecond=0)
    before_window = now - timedelta(days=2)
    within_window = now + timedelta(minutes=1)

    with Session() as session:
        place = Place(
            name="Fremont",
            state="CA",
            country="us",
            display_name="Fremont, CA",
            ocd_division_id="ocd-division/country:us/state:ca/place:fremont",
        )
        session.add(place)
        session.flush()

        old_event = Event(
            ocd_id="old-event",
            ocd_division_id=place.ocd_division_id,
            place_id=place.id,
            scraped_datetime=before_window,
            record_date=date(2026, 1, 1),
            source="fremont",
            source_url="https://example.com/old",
            name="Old meeting",
        )
        new_event = Event(
            ocd_id="new-event",
            ocd_division_id=place.ocd_division_id,
            place_id=place.id,
            scraped_datetime=within_window,
            record_date=date(2026, 2, 1),
            source="fremont",
            source_url="https://example.com/new",
            name="New meeting",
        )
        session.add_all([old_event, new_event])
        session.flush()

        preserved_catalog = Catalog(url_hash="preserved", location="/tmp/preserved.pdf")
        exclusive_catalog = Catalog(url_hash="exclusive", location="/tmp/exclusive.pdf")
        session.add_all([preserved_catalog, exclusive_catalog])
        session.flush()

        session.add_all(
            [
                Document(place_id=place.id, event_id=old_event.id, catalog_id=preserved_catalog.id, url="https://example.com/old.pdf", url_hash="preserved"),
                Document(place_id=place.id, event_id=new_event.id, catalog_id=preserved_catalog.id, url="https://example.com/new-shared.pdf", url_hash="new-shared"),
                Document(place_id=place.id, event_id=new_event.id, catalog_id=exclusive_catalog.id, url="https://example.com/new-exclusive.pdf", url_hash="exclusive"),
                Document(place_id=place.id, event_id=new_event.id, catalog_id=None, url="https://example.com/catalogless.pdf", url_hash="catalogless"),
            ]
        )
        session.add_all(
            [
                DataIssue(event_id=old_event.id, issue_type="preserved_issue"),
                DataIssue(event_id=new_event.id, issue_type="deleted_issue"),
            ]
        )
        session.commit()

    result = reset_city_verification_state("fremont", now.strftime("%Y-%m-%dT%H:%M:%SZ"))

    assert result["city"] == "fremont"
    assert result["deleted_event_count"] == 1
    assert result["deleted_document_count"] == 3
    assert result["deleted_catalog_count"] == 1
    assert result["catalog_reference_count"] == 2
    assert result["deleted_data_issue_count"] == 1

    second = reset_city_verification_state("fremont", now.strftime("%Y-%m-%dT%H:%M:%SZ"))
    assert second["deleted_event_count"] == 0
    assert second["deleted_document_count"] == 0
    assert second["deleted_catalog_count"] == 0
    assert second["deleted_data_issue_count"] == 0

    with Session() as session:
        assert session.query(Event).count() == 1
        assert session.query(Document).count() == 1
        assert session.query(Catalog).count() == 1
        assert session.query(DataIssue).count() == 1
        remaining_event = session.query(Event).one()
        remaining_catalog = session.query(Catalog).one()
        remaining_issue = session.query(DataIssue).one()
        assert remaining_event.ocd_id == "old-event"
        assert remaining_catalog.url_hash == "preserved"
        assert remaining_issue.issue_type == "preserved_issue"


def test_rewind_pending_city_onboarding_rejects_enabled_or_pass_city(mocker):
    mod = _load_rewind_module()
    mocker.patch.object(
        mod,
        "load_rollout_entry",
        return_value=type("RolloutEntry", (), {"enabled": "yes", "quality_gate": "pass"})(),
    )

    with pytest.raises(ValueError, match="disabled cities"):
        mod._validate_city_is_rewindable("hayward")


def test_reset_city_verification_state_does_not_delete_stage_rows(tmp_path, monkeypatch):
    Session = _setup_city_graph(tmp_path / "stage_guard.sqlite", monkeypatch)
    now = datetime.now(UTC).replace(tzinfo=None, microsecond=0)

    with Session() as session:
        place = Place(
            name="Fremont",
            state="CA",
            country="us",
            display_name="Fremont, CA",
            ocd_division_id="ocd-division/country:us/state:ca/place:fremont",
        )
        session.add(place)
        session.flush()
        session.add(EventStage(ocd_division_id=place.ocd_division_id, name="Stage", scraped_datetime=now))
        session.add(UrlStage(ocd_division_id=place.ocd_division_id, event="Stage", event_date=date(2026, 4, 4), url="https://example.com/a.pdf", url_hash="a", category="agenda"))
        session.add(UrlStageHist(ocd_division_id=place.ocd_division_id, event="Stage", event_date=date(2026, 4, 4), url="https://example.com/a.pdf", url_hash="a", category="agenda"))
        session.add(
            Event(
                ocd_id="event-1",
                ocd_division_id=place.ocd_division_id,
                place_id=place.id,
                scraped_datetime=now + timedelta(minutes=1),
                record_date=date(2026, 4, 4),
                source="fremont",
                source_url="https://example.com/event",
                name="Meeting",
            )
        )
        session.commit()

    reset_city_verification_state("fremont", now.strftime("%Y-%m-%dT%H:%M:%SZ"))

    with Session() as session:
        assert session.query(EventStage).count() == 1
        assert session.query(UrlStage).count() == 1
        assert session.query(UrlStageHist).count() == 1


def test_reset_city_verification_state_rolls_back_live_deletes_on_late_failure(tmp_path, monkeypatch):
    Session = _setup_city_graph(tmp_path / "reset_rollback.sqlite", monkeypatch)
    since = datetime(2026, 3, 15, 13, 21, 9)

    with Session() as session:
        place = Place(
            name="Fremont",
            state="CA",
            country="us",
            display_name="Fremont, CA",
            ocd_division_id="ocd-division/country:us/state:ca/place:fremont",
        )
        session.add(place)
        session.flush()
        event = Event(
            ocd_id="rollback-event",
            ocd_division_id=place.ocd_division_id,
            place_id=place.id,
            scraped_datetime=since + timedelta(minutes=1),
            record_date=date(2026, 4, 4),
            source="fremont",
            source_url="https://example.com/rollback",
            name="Rollback meeting",
        )
        catalog = Catalog(url_hash="rollback", location="/tmp/rollback.pdf")
        session.add_all([event, catalog])
        session.flush()
        session.add(
            Document(
                place_id=place.id,
                event_id=event.id,
                catalog_id=catalog.id,
                url_hash="rollback",
            )
        )
        session.add(DataIssue(event_id=event.id, issue_type="rollback_issue"))
        session.commit()
        session.execute(
            text(
                "CREATE TRIGGER abort_catalog_delete "
                "BEFORE DELETE ON catalog "
                "BEGIN SELECT RAISE(ABORT, 'catalog delete blocked'); END"
            )
        )
        session.commit()

    with pytest.raises(IntegrityError, match="catalog delete blocked"):
        reset_city_verification_state("fremont", since.strftime("%Y-%m-%dT%H:%M:%SZ"))

    with Session() as session:
        assert session.query(Event).count() == 1
        assert session.query(Document).count() == 1
        assert session.query(Catalog).count() == 1
        assert session.query(DataIssue).count() == 1

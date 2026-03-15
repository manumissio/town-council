from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import pipeline.db_session as db_session_module
from pipeline.models import Base, Catalog, Document, Event, Place
from scripts.reset_city_verification_state import capture_city_verification_baseline, reset_city_verification_state


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
                Document(place_id=place.id, event_id=new_event.id, catalog_id=exclusive_catalog.id, url="https://example.com/new-exclusive.pdf", url_hash="exclusive"),
            ]
        )
        session.commit()

    result = reset_city_verification_state("fremont", now.strftime("%Y-%m-%dT%H:%M:%SZ"))

    assert result["city"] == "fremont"
    assert result["deleted_event_count"] == 1
    assert result["deleted_document_count"] == 1
    assert result["deleted_catalog_count"] == 1
    assert result["catalog_reference_count"] == 1

    with Session() as session:
        assert session.query(Event).count() == 1
        assert session.query(Document).count() == 1
        assert session.query(Catalog).count() == 1
        remaining_event = session.query(Event).one()
        remaining_catalog = session.query(Catalog).one()
        assert remaining_event.ocd_id == "old-event"
        assert remaining_catalog.url_hash == "preserved"


def test_rewind_pending_city_onboarding_rejects_enabled_or_pass_city(mocker):
    mod = _load_rewind_module()
    mocker.patch.object(
        mod,
        "load_rollout_entry",
        return_value=type("RolloutEntry", (), {"enabled": "yes", "quality_gate": "pass"})(),
    )

    with pytest.raises(ValueError, match="disabled cities"):
        mod._validate_city_is_rewindable("hayward")


def test_capture_city_verification_baseline_reports_city_anchor(tmp_path, monkeypatch):
    Session = _setup_city_graph(tmp_path / "baseline.sqlite", monkeypatch)
    now = datetime.now(UTC).replace(tzinfo=None, microsecond=0)

    with Session() as session:
        place = Place(
            name="Sunnyvale",
            state="CA",
            country="us",
            display_name="Sunnyvale, CA",
            ocd_division_id="ocd-division/country:us/state:ca/place:sunnyvale",
        )
        session.add(place)
        session.flush()
        session.add_all(
            [
                Event(
                    ocd_id="early",
                    ocd_division_id=place.ocd_division_id,
                    place_id=place.id,
                    scraped_datetime=now,
                    record_date=date(2026, 3, 1),
                    source="sunnyvale",
                    source_url="https://example.com/early",
                    name="Early meeting",
                ),
                Event(
                    ocd_id="late",
                    ocd_division_id=place.ocd_division_id,
                    place_id=place.id,
                    scraped_datetime=now + timedelta(days=1),
                    record_date=date(2026, 3, 7),
                    source="sunnyvale",
                    source_url="https://example.com/late",
                    name="Late meeting",
                ),
            ]
        )
        session.commit()

    result = capture_city_verification_baseline("sunnyvale")

    assert result["city"] == "sunnyvale"
    assert result["baseline_event_count"] == 2
    assert result["baseline_max_record_date"] == "2026-03-07"
    assert result["baseline_max_scraped_datetime"] == (now + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")


def test_reset_city_verification_state_rewinds_to_baseline_record_date(tmp_path, monkeypatch):
    Session = _setup_city_graph(tmp_path / "anchor_reset.sqlite", monkeypatch)
    campaign_started_at = datetime(2026, 3, 15, 13, 21, 9)

    with Session() as session:
        place = Place(
            name="Sunnyvale",
            state="CA",
            country="us",
            display_name="Sunnyvale, CA",
            ocd_division_id="ocd-division/country:us/state:ca/place:sunnyvale",
        )
        session.add(place)
        session.flush()

        preserved_same_day = Event(
            ocd_id="baseline-same-day",
            ocd_division_id=place.ocd_division_id,
            place_id=place.id,
            scraped_datetime=campaign_started_at - timedelta(days=1),
            record_date=date(2026, 3, 10),
            source="sunnyvale",
            source_url="https://example.com/baseline-same-day",
            name="Baseline same-day meeting",
        )
        future_event = Event(
            ocd_id="future-run-one",
            ocd_division_id=place.ocd_division_id,
            place_id=place.id,
            scraped_datetime=campaign_started_at + timedelta(minutes=2),
            record_date=date(2026, 5, 18),
            source="sunnyvale",
            source_url="https://example.com/future",
            name="Future meeting",
        )
        same_day_run_one = Event(
            ocd_id="same-day-run-one",
            ocd_division_id=place.ocd_division_id,
            place_id=place.id,
            scraped_datetime=campaign_started_at + timedelta(minutes=3),
            record_date=date(2026, 3, 10),
            source="sunnyvale",
            source_url="https://example.com/same-day-run-one",
            name="Same day run-one meeting",
        )
        session.add_all([preserved_same_day, future_event, same_day_run_one])
        session.flush()

        future_catalog = Catalog(url_hash="future", location="/tmp/future.pdf")
        same_day_catalog = Catalog(url_hash="same-day", location="/tmp/same-day.pdf")
        session.add_all([future_catalog, same_day_catalog])
        session.flush()
        session.add_all(
            [
                Document(place_id=place.id, event_id=future_event.id, catalog_id=future_catalog.id, url_hash="future"),
                Document(place_id=place.id, event_id=same_day_run_one.id, catalog_id=same_day_catalog.id, url_hash="same-day"),
            ]
        )
        session.commit()

    result = reset_city_verification_state(
        "sunnyvale",
        campaign_started_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        baseline_record_date="2026-03-10",
    )

    assert result["deleted_event_count"] == 2
    assert result["deleted_document_count"] == 2
    assert result["deleted_catalog_count"] == 2
    assert result["remaining_event_count"] == 1
    assert result["remaining_max_record_date"] == "2026-03-10"
    assert result["remaining_max_scraped_datetime"] == (campaign_started_at - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")

    with Session() as session:
        remaining_events = session.query(Event).all()
        assert [event.ocd_id for event in remaining_events] == ["baseline-same-day"]

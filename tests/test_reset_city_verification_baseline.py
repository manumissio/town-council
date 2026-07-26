from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import pipeline.db_session as db_session_module
from pipeline.models import Base, Catalog, Document, Event, Place
from scripts import reset_city_verification_state as reset_module
from scripts.reset_city_verification_state import (
    capture_city_verification_baseline,
    reset_city_verification_state,
)


def _setup_city_graph(db_path: Path, monkeypatch) -> sessionmaker:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    db_session_module._SessionLocal = None
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def test_verification_reset_parser_returns_aware_utc():
    parsed_at = reset_module._parse_iso_utc("2026-03-15T13:21:09Z")

    assert parsed_at == datetime(2026, 3, 15, 13, 21, 9, tzinfo=UTC)
    assert parsed_at.utcoffset() == timedelta(0)


def test_verification_artifacts_normalize_offset_timestamps_to_utc(monkeypatch, mocker):
    offset_timestamp = datetime(
        2026,
        7,
        25,
        5,
        30,
        tzinfo=timezone(timedelta(hours=-7)),
    )
    session = mocker.MagicMock()
    session.query.return_value.filter.return_value.one.return_value = (
        date(2026, 7, 25),
        offset_timestamp,
        1,
    )

    @contextmanager
    def verification_session():
        yield session

    monkeypatch.setattr(reset_module, "db_session", verification_session)

    baseline = reset_module.capture_city_verification_baseline("sunnyvale")
    remaining = reset_module._remaining_anchor_summary(session, "sunnyvale")

    assert baseline["baseline_max_scraped_datetime"] == "2026-07-25T12:30:00Z"
    assert remaining["remaining_max_scraped_datetime"] == "2026-07-25T12:30:00Z"


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
    assert result["baseline_max_scraped_datetime"] == (now + timedelta(days=1)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


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
                Document(
                    place_id=place.id,
                    event_id=future_event.id,
                    catalog_id=future_catalog.id,
                    url_hash="future",
                ),
                Document(
                    place_id=place.id,
                    event_id=same_day_run_one.id,
                    catalog_id=same_day_catalog.id,
                    url_hash="same-day",
                ),
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
    assert result["remaining_max_scraped_datetime"] == (
        campaign_started_at - timedelta(days=1)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")

    with Session() as session:
        remaining_events = session.query(Event).all()
        assert [event.ocd_id for event in remaining_events] == ["baseline-same-day"]

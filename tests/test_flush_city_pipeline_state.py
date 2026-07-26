from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

import pipeline.db_session as db_session_module
from pipeline.models import Base, Catalog, DataIssue, Document, Event, EventStage, Place, UrlStage, UrlStageHist
from scripts.flush_city_pipeline_state import flush_city_pipeline_state


TEST_SCRAPED_AT = datetime(2026, 4, 4, 12, tzinfo=UTC)


def _setup_session(db_path: Path, monkeypatch) -> sessionmaker:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    db_session_module._SessionLocal = None
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def test_flush_city_pipeline_state_dry_run_reports_counts_without_deleting(tmp_path, monkeypatch):
    Session = _setup_session(tmp_path / "flush_dry_run.sqlite", monkeypatch)

    with Session() as session:
        place = Place(
            name="San Leandro",
            state="CA",
            country="us",
            display_name="San Leandro, CA",
            ocd_division_id="ocd-division/country:us/state:ca/place:san_leandro",
        )
        session.add(place)
        session.flush()

        session.add(
            EventStage(
                ocd_division_id=place.ocd_division_id,
                name="Stage",
                scraped_datetime=TEST_SCRAPED_AT,
            )
        )
        session.add(UrlStage(ocd_division_id=place.ocd_division_id, event="Stage", event_date=date(2026, 4, 4), url="https://example.com/a.pdf", url_hash="a", category="agenda"))
        session.add(UrlStageHist(ocd_division_id=place.ocd_division_id, event="Stage", event_date=date(2026, 4, 4), url="https://example.com/a.pdf", url_hash="a", category="agenda"))

        event = Event(
            ocd_id="event-1",
            ocd_division_id=place.ocd_division_id,
            place_id=place.id,
            scraped_datetime=TEST_SCRAPED_AT,
            record_date=date(2026, 4, 4),
            source="san_leandro",
            source_url="https://example.com/event",
            name="Meeting",
        )
        catalog = Catalog(url_hash="catalog-a", location="/tmp/a.pdf")
        session.add_all([event, catalog])
        session.flush()
        session.add(Document(place_id=place.id, event_id=event.id, catalog_id=catalog.id, url_hash="catalog-a"))
        session.add(DataIssue(event_id=event.id, issue_type="broken_link"))
        session.commit()

    result = flush_city_pipeline_state("san_leandro", dry_run=True)

    assert result["dry_run"] is True
    assert result["deleted_event_stage_count"] == 1
    assert result["deleted_url_stage_count"] == 1
    assert result["deleted_url_stage_hist_count"] == 1
    assert result["deleted_event_count"] == 1
    assert result["deleted_document_count"] == 1
    assert result["deleted_catalog_count"] == 1
    assert result["deleted_data_issue_count"] == 1
    assert result["remaining_event_count"] == 1
    assert result["remaining_event_stage_count"] == 1

    with Session() as session:
        assert session.query(EventStage).count() == 1
        assert session.query(UrlStage).count() == 1
        assert session.query(UrlStageHist).count() == 1
        assert session.query(Event).count() == 1
        assert session.query(Document).count() == 1
        assert session.query(Catalog).count() == 1
        assert session.query(DataIssue).count() == 1


def test_flush_city_pipeline_state_apply_deletes_city_scoped_stage_and_live_rows(tmp_path, monkeypatch):
    Session = _setup_session(tmp_path / "flush_apply.sqlite", monkeypatch)

    with Session() as session:
        target_place = Place(
            name="San Leandro",
            state="CA",
            country="us",
            display_name="San Leandro, CA",
            ocd_division_id="ocd-division/country:us/state:ca/place:san_leandro",
        )
        other_place = Place(
            name="Berkeley",
            state="CA",
            country="us",
            display_name="Berkeley, CA",
            ocd_division_id="ocd-division/country:us/state:ca/place:berkeley",
        )
        session.add_all([target_place, other_place])
        session.flush()

        session.add_all(
            [
                EventStage(
                    ocd_division_id=target_place.ocd_division_id,
                    name="Target",
                    scraped_datetime=TEST_SCRAPED_AT,
                ),
                EventStage(
                    ocd_division_id=other_place.ocd_division_id,
                    name="Other",
                    scraped_datetime=TEST_SCRAPED_AT,
                ),
                UrlStage(ocd_division_id=target_place.ocd_division_id, event="Target", event_date=date(2026, 4, 4), url="https://example.com/target.pdf", url_hash="target-stage", category="agenda"),
                UrlStage(ocd_division_id=other_place.ocd_division_id, event="Other", event_date=date(2026, 4, 4), url="https://example.com/other.pdf", url_hash="other-stage", category="agenda"),
                UrlStageHist(ocd_division_id=target_place.ocd_division_id, event="Target", event_date=date(2026, 4, 4), url="https://example.com/target.pdf", url_hash="target-stage", category="agenda"),
                UrlStageHist(ocd_division_id=other_place.ocd_division_id, event="Other", event_date=date(2026, 4, 4), url="https://example.com/other.pdf", url_hash="other-stage", category="agenda"),
            ]
        )

        target_event = Event(
            ocd_id="target-event",
            ocd_division_id=target_place.ocd_division_id,
            place_id=target_place.id,
            scraped_datetime=TEST_SCRAPED_AT,
            record_date=date(2026, 4, 4),
            source="san_leandro",
            source_url="https://example.com/target-event",
            name="Target meeting",
        )
        other_event = Event(
            ocd_id="other-event",
            ocd_division_id=other_place.ocd_division_id,
            place_id=other_place.id,
            scraped_datetime=TEST_SCRAPED_AT,
            record_date=date(2026, 4, 4),
            source="berkeley",
            source_url="https://example.com/other-event",
            name="Other meeting",
        )
        shared_catalog = Catalog(url_hash="shared", location="/tmp/shared.pdf")
        target_only_catalog = Catalog(url_hash="target-only", location="/tmp/target.pdf")
        session.add_all([target_event, other_event, shared_catalog, target_only_catalog])
        session.flush()
        session.add_all(
            [
                Document(place_id=target_place.id, event_id=target_event.id, catalog_id=shared_catalog.id, url_hash="shared"),
                Document(place_id=other_place.id, event_id=other_event.id, catalog_id=shared_catalog.id, url_hash="shared"),
                Document(place_id=target_place.id, event_id=target_event.id, catalog_id=target_only_catalog.id, url_hash="target-only"),
                Document(place_id=target_place.id, event_id=target_event.id, catalog_id=None, url_hash="catalogless"),
            ]
        )
        session.add_all(
            [
                DataIssue(event_id=target_event.id, issue_type="broken_link"),
                DataIssue(event_id=other_event.id, issue_type="other_city_issue"),
            ]
        )
        session.commit()

    result = flush_city_pipeline_state("san_leandro", dry_run=False)

    assert result["dry_run"] is False
    assert result["deleted_event_stage_count"] == 1
    assert result["deleted_url_stage_count"] == 1
    assert result["deleted_url_stage_hist_count"] == 1
    assert result["deleted_event_count"] == 1
    assert result["deleted_document_count"] == 3
    assert result["deleted_catalog_count"] == 1
    assert result["catalog_reference_count"] == 2
    assert result["deleted_data_issue_count"] == 1
    assert result["remaining_event_count"] == 0
    assert result["remaining_document_count"] == 0
    assert result["remaining_catalog_count"] == 0
    assert result["remaining_event_stage_count"] == 0
    assert result["remaining_url_stage_count"] == 0
    assert result["remaining_url_stage_hist_count"] == 0

    second = flush_city_pipeline_state("san_leandro", dry_run=False)
    assert second["deleted_event_stage_count"] == 0
    assert second["deleted_url_stage_count"] == 0
    assert second["deleted_url_stage_hist_count"] == 0
    assert second["deleted_event_count"] == 0
    assert second["deleted_document_count"] == 0
    assert second["deleted_catalog_count"] == 0

    with Session() as session:
        assert session.query(EventStage).count() == 1
        assert session.query(UrlStage).count() == 1
        assert session.query(UrlStageHist).count() == 1
        assert session.query(Event).count() == 1
        assert session.query(Document).count() == 1
        assert session.query(Catalog).count() == 1
        assert session.query(Catalog).one().url_hash == "shared"
        assert session.query(DataIssue).count() == 1
        assert session.query(DataIssue).one().issue_type == "other_city_issue"


def test_flush_city_pipeline_state_rolls_back_stage_and_live_deletes_on_late_failure(tmp_path, monkeypatch):
    Session = _setup_session(tmp_path / "flush_rollback.sqlite", monkeypatch)

    with Session() as session:
        place = Place(
            name="San Leandro",
            state="CA",
            country="us",
            display_name="San Leandro, CA",
            ocd_division_id="ocd-division/country:us/state:ca/place:san_leandro",
        )
        session.add(place)
        session.flush()
        event = Event(
            ocd_id="rollback-event",
            ocd_division_id=place.ocd_division_id,
            place_id=place.id,
            scraped_datetime=TEST_SCRAPED_AT,
            record_date=date(2026, 4, 4),
            source="san_leandro",
            source_url="https://example.com/rollback",
            name="Rollback meeting",
        )
        catalog = Catalog(url_hash="rollback", location="/tmp/rollback.pdf")
        session.add_all(
            [
                EventStage(
                    ocd_division_id=place.ocd_division_id,
                    name="Rollback stage",
                    scraped_datetime=TEST_SCRAPED_AT,
                ),
                event,
                catalog,
            ]
        )
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
        flush_city_pipeline_state("san_leandro", dry_run=False)

    with Session() as session:
        assert session.query(EventStage).count() == 1
        assert session.query(Event).count() == 1
        assert session.query(Document).count() == 1
        assert session.query(Catalog).count() == 1
        assert session.query(DataIssue).count() == 1


def test_flush_city_pipeline_state_rejects_invalid_city_slug():
    with pytest.raises(ValueError, match="invalid city slug"):
        flush_city_pipeline_state("San Leandro", dry_run=True)

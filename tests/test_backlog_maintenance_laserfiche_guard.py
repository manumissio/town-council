import sys
from contextlib import contextmanager
from unittest.mock import MagicMock

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.modules["llama_cpp"] = MagicMock()

from pipeline import backlog_maintenance as mod
from pipeline.models import Base, Catalog, Document, Event, Place


def _session_fixture(mocker):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    @contextmanager
    def fake_db_session():
        session = Session()
        try:
            yield session
        finally:
            session.close()

    mocker.patch.object(mod, "db_session", fake_db_session)
    return Session


def test_segment_catalog_with_mode_marks_laserfiche_error_content_failed(mocker):
    Session = _session_fixture(mocker)
    session = Session()
    place = Place(
        name="San Mateo",
        state="CA",
        ocd_division_id="ocd-division/country:us/state:ca/place:san_mateo",
        crawler_name="san_mateo",
    )
    session.add(place)
    session.flush()
    event = Event(place_id=place.id, ocd_division_id=place.ocd_division_id, source="san_mateo", name="Agenda")
    session.add(event)
    session.flush()
    catalog = Catalog(
        url_hash="hash-1",
        location="/tmp/agenda.html",
        url="https://portal.laserfiche.com/Portal/DocView.aspx?id=1",
        content=(
            "The system has encountered an error and could not complete your request. "
            "If the problem persists, please contact the site administrator."
        ),
    )
    session.add(catalog)
    session.flush()
    session.add(Document(place_id=place.id, event_id=event.id, catalog_id=catalog.id, category="agenda", url=catalog.url))
    session.commit()
    catalog_id = catalog.id
    session.close()

    result = mod.segment_catalog_with_mode(catalog_id, segment_mode="maintenance")

    assert result["status"] == "failed"
    assert result["error"] == "laserfiche_error_page_detected"

    check = Session()
    refreshed = check.get(Catalog, catalog_id)
    assert refreshed.agenda_segmentation_status == "failed"
    assert refreshed.agenda_segmentation_error == "laserfiche_error_page_detected"
    assert refreshed.agenda_segmentation_item_count == 0
    check.close()


def test_build_deterministic_agenda_summary_payload_blocks_laserfiche_error_content(mocker):
    Session = _session_fixture(mocker)
    session = Session()
    catalog = Catalog(
        url_hash="hash-2",
        location="/tmp/agenda.html",
        url="https://portal.laserfiche.com/Portal/DocView.aspx?id=2",
        content=(
            "The system has encountered an error and could not complete your request. "
            "If the problem persists, please contact the site administrator."
        ),
    )
    session.add(catalog)
    session.commit()
    catalog_id = catalog.id
    session.close()

    result = mod.build_deterministic_agenda_summary_payload(catalog_id)

    assert result == {"status": "error", "error": "laserfiche_error_page_detected"}


def test_segment_catalog_with_mode_marks_laserfiche_loading_shell_failed(mocker):
    Session = _session_fixture(mocker)
    session = Session()
    place = Place(
        name="San Mateo",
        state="CA",
        ocd_division_id="ocd-division/country:us/state:ca/place:san_mateo",
        crawler_name="san_mateo",
    )
    session.add(place)
    session.flush()
    event = Event(place_id=place.id, ocd_division_id=place.ocd_division_id, source="san_mateo", name="Agenda")
    session.add(event)
    session.flush()
    catalog = Catalog(
        url_hash="hash-3",
        location="/tmp/agenda.html",
        url="https://portal.laserfiche.com/Portal/DocView.aspx?id=3",
        content="[PAGE 1] Loading... The URL can be used to link to this page Your browser does not support the video tag.",
    )
    session.add(catalog)
    session.flush()
    session.add(Document(place_id=place.id, event_id=event.id, catalog_id=catalog.id, category="agenda", url=catalog.url))
    session.commit()
    catalog_id = catalog.id
    session.close()

    result = mod.segment_catalog_with_mode(catalog_id, segment_mode="maintenance")

    assert result["status"] == "failed"
    assert result["error"] == "laserfiche_loading_shell_detected"

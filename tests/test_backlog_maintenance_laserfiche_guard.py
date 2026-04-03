import sys
from contextlib import contextmanager
from unittest.mock import MagicMock

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.modules["llama_cpp"] = MagicMock()

from pipeline import backlog_maintenance as mod
from pipeline.models import AgendaItem, Base, Catalog, Document, Event, Place


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


def test_segment_catalog_with_mode_marks_single_item_staff_report_failed(mocker):
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
        url_hash="hash-4",
        location="/tmp/agenda.pdf",
        url="https://portal.laserfiche.com/Portal/ElectronicFile.aspx?docid=4",
        content=(
            "CITY OF SAN MATEO\nAgenda Report\nAgenda Number: 8\nSection Name: NEW BUSINESS\n"
            "TO: City Council\nFROM: Alex Khojikian, City Manager\n"
            "SUBJECT: Boards and Commissions Vacancy Process\n"
            "RECOMMENDATION: Approve the revised vacancy process."
        ),
    )
    session.add(catalog)
    session.flush()
    doc = Document(place_id=place.id, event_id=event.id, catalog_id=catalog.id, category="agenda", url=catalog.url)
    doc.event = event
    session.add(doc)
    session.commit()
    catalog_id = catalog.id
    session.close()

    mocker.patch.object(mod, "has_viable_structured_agenda_source", return_value=False)

    result = mod.segment_catalog_with_mode(catalog_id, segment_mode="maintenance")

    assert result["status"] == "failed"
    assert result["error"] == "single_item_staff_report_detected"

    check = Session()
    refreshed = check.get(Catalog, catalog_id)
    assert refreshed.agenda_segmentation_status == "failed"
    assert refreshed.agenda_segmentation_error == "single_item_staff_report_detected"
    assert refreshed.agenda_segmentation_item_count == 0
    check.close()


def test_build_deterministic_agenda_summary_payloads_batches_callbacks_only_for_changed_catalogs(mocker):
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

    first_catalog = Catalog(
        url_hash="hash-5",
        location="/tmp/agenda-1.html",
        url="https://example.com/agenda-1",
        content="Agenda with housing discussion and public comment.",
    )
    second_catalog = Catalog(
        url_hash="hash-6",
        location="/tmp/agenda-2.html",
        url="https://example.com/agenda-2",
        content="Agenda with budget discussion and final reading.",
    )
    session.add_all([first_catalog, second_catalog])
    session.flush()
    session.add_all(
        [
            Document(place_id=place.id, event_id=event.id, catalog_id=first_catalog.id, category="agenda", url=first_catalog.url),
            Document(place_id=place.id, event_id=event.id, catalog_id=second_catalog.id, category="agenda", url=second_catalog.url),
            AgendaItem(catalog_id=first_catalog.id, event_id=event.id, order=1, title="Housing Update", description="Discuss housing pipeline.", page_number=1),
            AgendaItem(catalog_id=second_catalog.id, event_id=event.id, order=1, title="Budget Adoption", description="Adopt the annual budget.", page_number=1),
        ]
    )
    session.commit()

    seeded = mod.build_deterministic_agenda_summary_payload(first_catalog.id)
    assert seeded["status"] == "complete"

    reindex_spy = MagicMock(return_value={"catalogs_considered": 1, "catalogs_reindexed": 1, "catalogs_failed": 0, "failed_catalog_ids": []})
    embed_spy = MagicMock(return_value={"catalogs_considered": 1, "embed_enqueued": 1, "embed_dispatch_failed": 0, "failed_catalog_ids": []})

    result = mod.build_deterministic_agenda_summary_payloads(
        [first_catalog.id, second_catalog.id],
        reindex_callback=reindex_spy,
        embed_callback=embed_spy,
    )

    assert result["changed_catalog_ids"] == [second_catalog.id]
    reindex_spy.assert_called_once_with([second_catalog.id])
    embed_spy.assert_called_once_with([second_catalog.id])

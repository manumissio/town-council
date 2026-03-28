import sys
from unittest.mock import MagicMock

import pytest

sys.modules["llama_cpp"] = MagicMock()

from sqlalchemy import and_, or_

from pipeline.agenda_worker import segment_document_agenda
from pipeline.models import AgendaItem, Catalog, Document, Event, Place


def _build_minimal_meeting(db_session):
    place = Place(name="Test City", state="CA", ocd_division_id="ocd-city")
    db_session.add(place)
    db_session.flush()

    event = Event(name="Test Meeting", place_id=place.id, ocd_division_id="ocd-city")
    db_session.add(event)
    db_session.flush()

    catalog = Catalog(
        filename="test.pdf",
        url_hash="test_hash_123",
        content="Agenda text",
        url="http://test.com/test.pdf",
    )
    db_session.add(catalog)
    db_session.flush()

    doc = Document(event_id=event.id, catalog_id=catalog.id, place_id=place.id, category="agenda")
    db_session.add(doc)
    db_session.commit()
    return place, event, doc, catalog


def test_segment_document_agenda_sets_empty_status_when_no_items(db_session, mocker):
    _, event, _, catalog = _build_minimal_meeting(db_session)

    mocker.patch("pipeline.agenda_worker.LocalAI", return_value=MagicMock())
    mocker.patch(
        "pipeline.agenda_worker.resolve_agenda_items",
        return_value={"items": [], "source_used": "llm", "quality_score": 0, "confidence": "low"},
    )

    segment_document_agenda(catalog.id)

    # segment_document_agenda uses its own session; clear identity-map cache.
    db_session.expire_all()
    refreshed = db_session.get(Catalog, catalog.id)
    assert refreshed.agenda_segmentation_status == "empty"
    assert refreshed.agenda_segmentation_item_count == 0
    assert db_session.query(AgendaItem).filter_by(catalog_id=catalog.id).count() == 0


def test_agenda_worker_selection_excludes_empty_status(db_session):
    place, event, _, catalog_empty = _build_minimal_meeting(db_session)
    catalog_empty.agenda_segmentation_status = "empty"
    db_session.commit()

    catalog_todo = Catalog(
        filename="todo.pdf",
        url_hash="todo_hash",
        content="Agenda text",
        url="http://test.com/todo.pdf",
    )
    db_session.add(catalog_todo)
    db_session.flush()
    doc2 = Document(event_id=event.id, catalog_id=catalog_todo.id, place_id=place.id)
    db_session.add(doc2)
    db_session.commit()

    to_process = (
        db_session.query(Catalog)
        .join(Document, Catalog.id == Document.catalog_id)
        .outerjoin(AgendaItem, Catalog.id == AgendaItem.catalog_id)
        .filter(
            Catalog.content != None,
            Catalog.content != "",
            or_(
                Catalog.agenda_segmentation_status == None,
                Catalog.agenda_segmentation_status == "failed",
                and_(
                    Catalog.agenda_segmentation_status == "complete",
                    AgendaItem.page_number == None,
                ),
            ),
        )
        .all()
    )

    ids = {c.id for c in to_process}
    assert catalog_empty.id not in ids
    assert catalog_todo.id in ids


def test_segment_document_agenda_marks_single_item_staff_report_failed(db_session, mocker):
    _, _event, _doc, catalog = _build_minimal_meeting(db_session)
    catalog.content = (
        "CITY OF SAN MATEO\nAgenda Report\nAgenda Number: 8\nSection Name: NEW BUSINESS\n"
        "TO: City Council\nFROM: Alex Khojikian, City Manager\n"
        "SUBJECT: Boards and Commissions Vacancy Process\n"
        "RECOMMENDATION: Approve the revised vacancy process."
    )
    db_session.commit()

    mocker.patch("pipeline.agenda_worker.has_viable_structured_agenda_source", return_value=False)
    mocker.patch("pipeline.agenda_worker.LocalAI", return_value=MagicMock())

    segment_document_agenda(catalog.id)

    db_session.expire_all()
    refreshed = db_session.get(Catalog, catalog.id)
    assert refreshed.agenda_segmentation_status == "failed"
    assert refreshed.agenda_segmentation_error == "single_item_staff_report_detected"
    assert refreshed.agenda_segmentation_item_count == 0
    assert db_session.query(AgendaItem).filter_by(catalog_id=catalog.id).count() == 0

import pytest
from unittest.mock import MagicMock
import sys

sys.modules["llama_cpp"] = MagicMock()
from pipeline.agenda_worker import segment_document_agenda
from pipeline.models import Place, Event, Document, Catalog, AgendaItem

def test_agenda_segmentation_logic(db_session, mocker):
    """
    Test: Does the agenda worker persist resolved agenda items?
    """
    # 1. Setup Data
    place = Place(name="Test City", state="CA", ocd_division_id="ocd-city")
    db_session.add(place)
    db_session.flush()

    event = Event(name="Test Meeting", place_id=place.id, ocd_division_id="ocd-city")
    db_session.add(event)
    db_session.flush()

    catalog = Catalog(
        filename="test.pdf",
        url_hash="test_hash_123",
        content="This is the raw text of an agenda. Item 1: Zoning. Item 2: Budget.",
        url="http://test.com/test.pdf"
    )
    db_session.add(catalog)
    db_session.flush()

    doc = Document(event_id=event.id, catalog_id=catalog.id, place_id=place.id)
    db_session.add(doc)
    db_session.commit()

    # 2. Mock resolver output (Legistar-first path)
    mocker.patch("pipeline.agenda_worker.LocalAI", return_value=MagicMock())
    mocker.patch("pipeline.agenda_worker.resolve_agenda_items", return_value={
        "items": [
            {"order": 1, "title": "Zoning Change", "description": "Discussion about Main St", "classification": "Action", "result": "Passed", "page_number": 4},
            {"order": 2, "title": "Budget 2026", "description": "Reviewing fiscal goals", "classification": "Discussion", "result": "", "page_number": 6},
        ],
        "source_used": "legistar",
        "quality_score": 81,
        "confidence": "high",
    })

    # 3. Action: Run the segmentation logic
    segment_document_agenda(catalog.id)

    # 4. Verify: Did it save to the database?
    items = db_session.query(AgendaItem).filter_by(catalog_id=catalog.id).order_by(AgendaItem.order).all()
    
    assert len(items) == 2
    assert items[0].title == "Zoning Change"
    assert items[0].classification == "Action"
    assert items[0].page_number == 4
    assert items[1].title == "Budget 2026"
    assert items[1].event_id == event.id

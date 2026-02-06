import pytest
import json
import sys
import os
from unittest.mock import MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Setup paths
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(root_dir)
sys.path.append(os.path.join(root_dir, 'pipeline'))

from pipeline.models import Base, Catalog, AgendaItem, Event, Document, Place
from pipeline.agenda_worker import segment_agendas

@pytest.fixture
def db_session():
    """Temporary in-memory database."""
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def test_agenda_segmentation_logic(db_session, mocker, monkeypatch):
    """
    Test: Does the agenda worker correctly parse AI JSON and save items?
    """
    # 1. Setup Data
    monkeypatch.setenv("GEMINI_API_KEY", "fake_key")
    
    place = Place(name="Test City", state="CA", ocd_division_id="ocd-city")
    db_session.add(place)
    db_session.flush()
    
    event = Event(name="Test Meeting", place_id=place.id, ocd_division_id="ocd-city")
    db_session.add(event)
    db_session.flush()
    
    catalog = Catalog(
        filename="test.pdf",
        content="This is the raw text of an agenda. Item 1: Zoning. Item 2: Budget.",
        url="http://test.com/test.pdf"
    )
    db_session.add(catalog)
    db_session.flush()
    
    doc = Document(event_id=event.id, catalog_id=catalog.id, place_id=place.id)
    db_session.add(doc)
    db_session.commit()

    # 2. Mock Gemini Response
    mock_items = [
        {"order": 1, "title": "Zoning Change", "description": "Discussion about Main St", "classification": "Action", "result": "Passed"},
        {"order": 2, "title": "Budget 2026", "description": "Reviewing fiscal goals", "classification": "Discussion", "result": ""}
    ]
    
    mock_response = MagicMock()
    mock_response.text = json.dumps(mock_items)
    
    # Mock the GenAI client
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response
    mocker.patch('pipeline.agenda_worker.genai.Client', return_value=mock_client)
    mocker.patch('pipeline.agenda_worker.db_connect', return_value=db_session.get_bind())

    # 3. Action
    segment_agendas()

    # 4. Verify
    items = db_session.query(AgendaItem).filter_by(event_id=event.id).all()
    assert len(items) == 2
    assert items[0].title == "Zoning Change"
    assert items[0].result == "Passed"
    assert items[1].title == "Budget 2026"
    assert items[1].ocd_id.startswith("ocd-agendaitem/")

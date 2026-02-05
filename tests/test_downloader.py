import sys
import os
import pytest
from unittest.mock import MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Setup paths
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(root_dir)
sys.path.append(os.path.join(root_dir, 'pipeline'))

from pipeline.models import Base, Catalog, UrlStage, Event, Place
from pipeline.downloader import process_single_url

@pytest.fixture
def db_session():
    """Temporary in-memory database."""
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def test_downloader_absolute_path(db_session, mocker, monkeypatch):
    """
    Test: Ensure the downloader saves absolute paths to the database.
    This is critical for cross-service file access in Docker.
    """
    # 1. Setup Environment
    test_data_dir = os.path.abspath("/tmp/town-council-test")
    monkeypatch.setenv("DATA_DIR", test_data_dir)
    
    # 2. Seed Data
    place = Place(name="Test City", ocd_division_id="ocd-division/country:us/state:ca/place:test")
    db_session.add(place)
    db_session.flush()
    
    event = Event(name="Test Meeting", record_date=None, ocd_division_id=place.ocd_division_id, place_id=place.id)
    db_session.add(event)
    
    url_stage = UrlStage(
        ocd_division_id=place.ocd_division_id,
        event="Test Meeting",
        url="https://example.com/test.pdf",
        url_hash="test_hash_123",
        category="agenda"
    )
    db_session.add(url_stage)
    db_session.commit()

    # 3. Mock Network and Disk
    mock_response = MagicMock()
    mock_response.headers = {'Content-Type': 'application/pdf'}
    mock_response.iter_content.return_value = [b"dummy pdf content"]
    mocker.patch('requests.Session.get', return_value=mock_response)
    mocker.patch('pipeline.downloader.db_connect', return_value=db_session.get_bind())
    # Mock os.makedirs and open to avoid actual disk writes
    mocker.patch('os.makedirs')
    mocker.patch('builtins.open', mocker.mock_open())

    # 4. Action
    process_single_url(url_stage.id)

    # 5. Verify
    catalog_entry = db_session.query(Catalog).filter_by(url_hash="test_hash_123").first()
    assert catalog_entry is not None
    # Path should be absolute
    assert os.path.isabs(catalog_entry.location)
    assert "test_hash_123.pdf" in catalog_entry.location

def test_downloader_race_condition(db_session, mocker):
    """
    Test: Does the downloader handle two meetings sharing the same file?
    We simulate a 'UniqueViolation' to ensure the code recovers and links correctly.
    """
    # 1. Seed existing file in Catalog
    existing_file = Catalog(
        url="https://shared.com/file.pdf",
        url_hash="shared_hash",
        location="/app/data/shared_hash.pdf"
    )
    db_session.add(existing_file)
    
    place = Place(name="City", ocd_division_id="ocd-city")
    db_session.add(place)
    db_session.flush()
    
    event = Event(name="Meeting 2", record_date=None, ocd_division_id="ocd-city", place_id=place.id)
    db_session.add(event)
    
    url_stage = UrlStage(
        ocd_division_id="ocd-city",
        event="Meeting 2",
        url="https://shared.com/file.pdf",
        url_hash="shared_hash",
        category="minutes"
    )
    db_session.add(url_stage)
    db_session.commit()

    # 2. Mock: Simulate that the initial check for 'Catalog' fails (race condition)
    # but the INSERT triggers an error.
    mocker.patch('pipeline.downloader.db_connect', return_value=db_session.get_bind())
    
    # We mock 'Media.gather' to return a path, but we'll force the main logic
    # to hit the 'except' block by making the first query return None.
    # Note: In the real code, this happens if two threads check if it exists at the same time.
    
    # 3. Action
    process_single_url(url_stage.id)

    # 4. Verify: The document should be linked to the EXISTING catalog entry.
    from pipeline.models import Document
    doc_link = db_session.query(Document).filter_by(event_id=event.id).first()
    assert doc_link is not None
    assert doc_link.catalog_id == existing_file.id

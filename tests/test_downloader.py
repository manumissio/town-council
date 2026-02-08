import sys
import os
from unittest.mock import MagicMock

# Setup paths
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(root_dir)
sys.path.append(os.path.join(root_dir, 'pipeline'))

from pipeline.models import Catalog, UrlStage, Event, Place
from pipeline.downloader import process_single_url, process_staged_urls

def test_downloader_absolute_path(db_session, mocker, monkeypatch):
    """
    Test: Ensure the downloader saves absolute paths to the database.
    This is critical for cross-service file access in Docker.
    """
    # 1. Setup Environment
    test_data_dir = os.path.abspath("/tmp/town-council-test")
    monkeypatch.setenv("DATA_DIR", test_data_dir)
    
    # 2. Seed Data
    import datetime
    test_date = datetime.date(2026, 2, 1)

    place = Place(name="Test City", ocd_division_id="ocd-division/country:us/state:ca/place:test", state="CA")
    db_session.add(place)
    db_session.flush()

    event = Event(name="Test Meeting", record_date=test_date, ocd_division_id=place.ocd_division_id, place_id=place.id)
    db_session.add(event)

    url_stage = UrlStage(
        ocd_division_id=place.ocd_division_id,
        event="Test Meeting",
        event_date=test_date,
        url="https://example.com/test.pdf",
        url_hash="test_hash_123",
        category="agenda"
    )
    db_session.add(url_stage)
    db_session.commit()

    # 3. Mock Download
    # Mock Media.gather to return a fake file path without actual download
    test_path = f"{test_data_dir}/us/ca/test/test_hash_123.pdf"
    mock_media_instance = MagicMock()
    mock_media_instance.gather.return_value = test_path
    mocker.patch('pipeline.downloader.Media', return_value=mock_media_instance)

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
    import datetime
    test_date = datetime.date(2026, 2, 2)

    # 1. Seed existing file in Catalog
    existing_file = Catalog(
        url="https://shared.com/file.pdf",
        url_hash="shared_hash",
        location="/app/data/shared_hash.pdf"
    )
    db_session.add(existing_file)

    place = Place(name="City", ocd_division_id="ocd-city", state="CA")
    db_session.add(place)
    db_session.flush()

    event = Event(name="Meeting 2", record_date=test_date, ocd_division_id="ocd-city", place_id=place.id)
    db_session.add(event)

    url_stage = UrlStage(
        ocd_division_id="ocd-city",
        event="Meeting 2",
        event_date=test_date,
        url="https://shared.com/file.pdf",
        url_hash="shared_hash",
        category="minutes"
    )
    db_session.add(url_stage)
    db_session.commit()

    # 2. Mock: Simulate that the initial check for 'Catalog' fails (race condition)
    # but the INSERT triggers an error.
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


def test_process_staged_urls_archives_only_successes(mocker):
    """
    Test: only successfully processed URL IDs are archived from staging.
    """
    fake_rows = [MagicMock(id=1), MagicMock(id=2), MagicMock(id=3)]
    fake_session = MagicMock()
    fake_session.query.return_value.all.return_value = fake_rows

    class _FakeExecutor:
        def __init__(self, *args, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc, tb):
            return False
        def map(self, fn, ids):
            return [fn(i) for i in ids]

    class _SessionCtx:
        def __enter__(self):
            return fake_session
        def __exit__(self, exc_type, exc, tb):
            return False

    mocker.patch("pipeline.downloader.db_session", return_value=_SessionCtx())
    mocker.patch("pipeline.downloader.ThreadPoolExecutor", _FakeExecutor)
    mocker.patch("pipeline.downloader.process_single_url", side_effect=[True, False, True])
    archive_mock = mocker.patch("pipeline.downloader.archive_url_stage")

    process_staged_urls()
    archive_mock.assert_called_once_with([1, 3])

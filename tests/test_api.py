import pytest
from fastapi.testclient import TestClient
from fastapi import HTTPException
import sys
import os
from unittest.mock import MagicMock

# Add the project root to the path so we can import from api/main.py
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'api'))

# Mock heavy AI dependency before importing api.main
sys.modules["llama_cpp"] = MagicMock()

from api.main import app, get_local_ai, agenda_items_look_low_quality

# Override the AI dependency for the entire test module
mock_ai = MagicMock()
app.dependency_overrides[get_local_ai] = lambda: mock_ai

client = TestClient(app)
VALID_KEY = "dev_secret_key_change_me"

def test_read_root():
    """Test the root endpoint of the API."""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "message": "Town Council API is running. Go to /docs for the Swagger UI."}

def test_metadata_endpoint(mocker):
    """Test the /metadata endpoint correctly parses search engine facets."""
    mock_index = mocker.Mock()
    mock_index.search.return_value = {
        "facetDistribution": {
            "city": {"ca_berkeley": 10, "ca_dublin": 5},
            "organization": {"City Council": 15},
            "meeting_category": {"Regular": 10}
        }
    }
    mocker.patch("api.main.client.index", return_value=mock_index)
    
    response = client.get("/metadata", headers={"X-API-Key": VALID_KEY})
    assert response.status_code == 200
    data = response.json()
    
    # Check if cities are capitalized for the UI
    assert "Berkeley" in data["cities"]
    assert "Dublin" in data["cities"]
    assert "City Council" in data["organizations"]

def test_search_endpoint_params(mocker):
    """Test the /search endpoint handles query parameters correctly and builds filters."""
    mock_index = mocker.Mock()
    mock_index.search.return_value = {"hits": [], "estimatedTotalHits": 0}
    mocker.patch("api.main.client.index", return_value=mock_index)
    
    # Test with multiple filters
    response = client.get("/search?q=zoning&city=berkeley&meeting_type=Regular&limit=10&offset=5", headers={"X-API-Key": VALID_KEY})
    assert response.status_code == 200
    
    # Verify the parameters passed to Meilisearch search()
    mock_index.search.assert_called_once()
    args, _ = mock_index.search.call_args
    assert args[0] == "zoning"
    
    search_params = args[1]
    # Check if filters are correctly built
    # UI labels (e.g. "Berkeley") are normalized to the indexed facet key (e.g. "ca_berkeley").
    assert 'city = "ca_berkeley"' in search_params['filter']
    assert 'meeting_category = "Regular"' in search_params['filter']

def test_search_injection_protection(mocker):
    """
    Test: Does the search endpoint sanitize malicious filter strings?
    (Fixes Audit Issue #2)
    """
    mock_index = mocker.Mock()
    mock_index.search.return_value = {"hits": []}
    mocker.patch("api.main.client.index", return_value=mock_index)
    
    # Attempt a "Quote Escape" attack in the city parameter
    malicious_city = 'berkeley" OR 1=1 OR city="'
    client.get(f"/search?q=test&city={malicious_city}", headers={"X-API-Key": VALID_KEY})
    
    search_params = mock_index.search.call_args[0][1]
    # The double quote should be escaped: \"
    # Note: Meilisearch filters are lowercased in our implementation
    actual_filter = search_params['filter'][0]
    assert 'city = "berkeley\\"' in actual_filter
    assert 'or 1=1 or city=\\""' in actual_filter

def test_api_database_unavailable(mocker):
    """
    Test: Does the API return 503 if the database fails to load?
    """
    from api.main import get_db
    
    # 1. Simulate a failed DB initialization via dependency override
    def mock_get_db_fail():
        raise HTTPException(status_code=503, detail="Database service is unavailable")
    
    app.dependency_overrides[get_db] = mock_get_db_fail
    
    try:
        # 2. Action: Try to hit a DB-dependent endpoint
        response = client.get("/people", headers={"X-API-Key": VALID_KEY})
        
        # 3. Verify
        assert response.status_code == 503
        assert "Database service is unavailable" in response.json()["detail"]
    finally:
        # Cleanup: Remove the override so other tests pass
        del app.dependency_overrides[get_db]


def test_agenda_quality_gate_flags_low_quality_cache():
    """Low-quality cached agenda items should be considered stale."""
    bad_items = [
        MagicMock(title="", page_number=1),
        MagicMock(title="Special Closed Meeting 10/03/11", page_number=1),
        MagicMock(title="I hereby request that the City Clerk provide notice to each member.", page_number=1),
        MagicMock(title="state of emergency continues to directly impact the ability of the members to meet safely in person and", page_number=1),
    ]
    assert agenda_items_look_low_quality(bad_items) is True


def test_segment_force_bypasses_cache(mocker):
    """
    If cached agenda items exist, `force=true` should still enqueue regeneration.
    """
    from api.main import get_db, Catalog, AgendaItem

    catalog = MagicMock(id=401, content="City council meeting discussed budget updates and adopted multiple motions after public comment.")

    db = MagicMock()
    db.get.return_value = catalog
    query = db.query.return_value
    query.filter_by.return_value.order_by.return_value.all.return_value = [
        MagicMock(title="Budget Amendment", order=1)
    ]

    def _mock_get_db():
        yield db

    app.dependency_overrides[get_db] = _mock_get_db
    mocker.patch("api.main.agenda_items_look_low_quality", return_value=False)
    mock_task = MagicMock()
    mock_task.id = "task123"
    mocker.patch("api.main.segment_agenda_task.delay", return_value=mock_task)

    try:
        resp = client.post("/segment/401?force=true", headers={"X-API-Key": VALID_KEY})
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["status"] == "processing"
        assert payload["task_id"] == "task123"
    finally:
        del app.dependency_overrides[get_db]


def test_segment_returns_cached_when_not_forced_and_quality_ok(mocker):
    """
    Default behavior: if cache exists and doesn't look low quality, return cached items.
    """
    from api.main import get_db

    catalog = MagicMock(id=401, content="City council meeting discussed budget updates and adopted multiple motions after public comment.")
    existing = [MagicMock(title="Budget Amendment", order=1)]

    db = MagicMock()
    db.get.return_value = catalog
    query = db.query.return_value
    query.filter_by.return_value.order_by.return_value.all.return_value = existing

    def _mock_get_db():
        yield db

    app.dependency_overrides[get_db] = _mock_get_db
    mocker.patch("api.main.agenda_items_look_low_quality", return_value=False)
    mocker.patch("api.main.segment_agenda_task.delay")

    try:
        resp = client.post("/segment/401", headers={"X-API-Key": VALID_KEY})
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["status"] == "cached"
    finally:
        del app.dependency_overrides[get_db]


def test_summarize_force_bypasses_cache(mocker):
    """
    If a cached summary exists, `force=true` should still enqueue regeneration.
    """
    from api.main import get_db

    catalog = MagicMock(
        id=401,
        content="City council meeting discussed budget updates and adopted multiple motions after public comment.",
        summary="cached summary",
    )

    db = MagicMock()
    db.get.return_value = catalog

    def _mock_get_db():
        yield db

    app.dependency_overrides[get_db] = _mock_get_db
    mock_task = MagicMock()
    mock_task.id = "task_summary_1"
    mocker.patch("api.main.generate_summary_task.delay", return_value=mock_task)

    try:
        resp = client.post("/summarize/401?force=true", headers={"X-API-Key": VALID_KEY})
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["status"] == "processing"
        assert payload["task_id"] == "task_summary_1"
    finally:
        del app.dependency_overrides[get_db]


def test_summarize_returns_blocked_low_signal_without_queueing(mocker):
    from api.main import get_db

    catalog = MagicMock(id=909, content="Agenda", summary=None, content_hash="h1", summary_source_hash=None)
    db = MagicMock()
    db.get.return_value = catalog

    def _mock_get_db():
        yield db

    app.dependency_overrides[get_db] = _mock_get_db
    delay = mocker.patch("api.main.generate_summary_task.delay")
    try:
        resp = client.post("/summarize/909", headers={"X-API-Key": VALID_KEY})
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["status"] == "blocked_low_signal"
        assert "Not enough extracted text" in payload["reason"]
        delay.assert_not_called()
    finally:
        del app.dependency_overrides[get_db]


def test_topics_returns_blocked_low_signal_without_queueing(mocker):
    from api.main import get_db

    catalog = MagicMock(id=909, content="Agenda", topics=["Old"], content_hash="h1", topics_source_hash="h1")
    db = MagicMock()
    db.get.return_value = catalog

    def _mock_get_db():
        yield db

    app.dependency_overrides[get_db] = _mock_get_db
    delay = mocker.patch("api.main.generate_topics_task.delay")
    try:
        resp = client.post("/topics/909", headers={"X-API-Key": VALID_KEY})
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["status"] == "blocked_low_signal"
        assert "Not enough extracted text" in payload["reason"]
        assert payload["topics"] == []
        delay.assert_not_called()
    finally:
        del app.dependency_overrides[get_db]


def test_derived_status_exposes_blocked_reasons_for_low_signal_content():
    from api.main import get_db

    catalog = MagicMock(
        id=909,
        content="Agenda",
        content_hash="h1",
        summary="old summary",
        summary_source_hash="h1",
        topics=["Old"],
        topics_source_hash="h1",
    )
    db = MagicMock()
    db.get.return_value = catalog
    db.query.return_value.filter.return_value.count.return_value = 0

    def _mock_get_db():
        yield db

    app.dependency_overrides[get_db] = _mock_get_db
    try:
        resp = client.get("/catalog/909/derived_status", headers={"X-API-Key": VALID_KEY})
        assert resp.status_code == 200
        payload = resp.json()
        assert "Not enough extracted text" in payload["summary_blocked_reason"]
        assert "Not enough extracted text" in payload["topics_blocked_reason"]
        assert payload["agenda_not_generated_yet"] is True
    finally:
        del app.dependency_overrides[get_db]


def test_derived_status_exposes_not_generated_flags():
    from api.main import get_db

    catalog = MagicMock(
        id=911,
        content=(
            "The council discussed zoning reform, transportation safety, budget allocations, "
            "housing permits, environmental review, public works timelines, and procurement policy updates. "
            "Members reviewed implementation milestones, staffing impacts, and fiscal tradeoffs."
        ),
        content_hash="h1",
        summary=None,
        summary_source_hash=None,
        topics=[],
        topics_source_hash=None,
    )
    db = MagicMock()
    db.get.return_value = catalog
    db.query.return_value.filter.return_value.count.return_value = 0

    def _mock_get_db():
        yield db

    app.dependency_overrides[get_db] = _mock_get_db
    try:
        resp = client.get("/catalog/911/derived_status", headers={"X-API-Key": VALID_KEY})
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["summary_not_generated_yet"] is True
        assert payload["topics_not_generated_yet"] is True
        assert payload["agenda_not_generated_yet"] is True
        assert payload["summary_blocked_reason"] is None
        assert payload["topics_blocked_reason"] is None
    finally:
        del app.dependency_overrides[get_db]

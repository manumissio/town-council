import pytest
from fastapi.testclient import TestClient
from fastapi import HTTPException
import sys
import os

# Add the project root to the path so we can import from api/main.py
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'api'))

from api.main import app, get_local_ai

# SECURITY: Mock the heavy AI module to prevent library loading during tests
from unittest.mock import MagicMock
import sys

# We only mock llama_cpp to prevent C++ engine loading
sys.modules["llama_cpp"] = MagicMock()

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
    assert 'city = "berkeley"' in search_params['filter']
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




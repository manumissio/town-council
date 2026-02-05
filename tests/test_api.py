import pytest
from fastapi.testclient import TestClient
import sys
import os

# Add the project root to the path so we can import from api/main.py
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'api'))

from api.main import app

client = TestClient(app)

def test_read_root():
    """Test the root endpoint of the API."""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "message": "Town Council API is running. Go to /docs for the Swagger UI."}

def test_stats_endpoint(mocker):
    """Test the /stats endpoint with a mocked Meilisearch response."""
    # Mock the meilisearch client in main.py
    mock_index = mocker.Mock()
    mock_index.get_stats.return_value = {"numberOfDocuments": 100}
    mocker.patch("api.main.client.index", return_value=mock_index)
    
    response = client.get("/stats")
    assert response.status_code == 200
    assert response.json() == {"numberOfDocuments": 100}

def test_search_endpoint_params(mocker):
    """Test the /search endpoint handles query parameters correctly and builds filters."""
    mock_index = mocker.Mock()
    mock_index.search.return_value = {"hits": [], "estimatedTotalHits": 0}
    mocker.patch("api.main.client.index", return_value=mock_index)
    
    # Test with multiple filters
    # Note: we use city=berkeley and meeting_type=Regular
    response = client.get("/search?q=zoning&city=berkeley&meeting_type=Regular&limit=10&offset=5")
    assert response.status_code == 200
    
    # Verify the parameters passed to Meilisearch search()
    mock_index.search.assert_called_once()
    args, kwargs = mock_index.search.call_args
    assert args[0] == "zoning"
    
    search_params = args[1] # In our implementation, search_params is the second positional arg
    assert search_params['limit'] == 10
    assert search_params['offset'] == 5
    # Check if filters are correctly built in the search_params dictionary
    assert 'city = "berkeley"' in search_params['filter']
    assert 'meeting_category = "Regular"' in search_params['filter']

def test_search_date_filters(mocker):
    """Test that date filters are correctly formatted for Meilisearch strings."""
    mock_index = mocker.Mock()
    mock_index.search.return_value = {"hits": [], "estimatedTotalHits": 0}
    mocker.patch("api.main.client.index", return_value=mock_index)
    
    # Test date range
    client.get("/search?q=test&date_from=2026-01-01&date_to=2026-02-01")
    _, args = mock_index.search.call_args
    search_params = args[0] if isinstance(args, tuple) else args
    # Meilisearch client uses (query, params) or (query, **kwargs) depending on version.
    # Our code uses index.search(q, search_params)
    search_params = mock_index.search.call_args[0][1]
    
    assert 'date >= "2026-01-01" AND date <= "2026-02-01"' in search_params['filter']

def test_metadata_endpoint(mocker):
    """Test the /metadata endpoint correctly parses search engine facets."""
    mock_index = mocker.Mock()
    mock_index.search.return_value = {
        "facetDistribution": {
            "city": {"berkeley": 10, "dublin": 5},
            "organization": {"City Council": 15}
        }
    }
    mocker.patch("api.main.client.index", return_value=mock_index)
    
    response = client.get("/metadata")
    assert response.status_code == 200
    data = response.json()
    
    # Check if cities are capitalized for the UI
    assert "Berkeley" in data["cities"]
    assert "Dublin" in data["cities"]
    assert "City Council" in data["organizations"]

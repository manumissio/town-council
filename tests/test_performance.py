import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock
import sys

# Setup mocks
sys.modules["llama_cpp"] = MagicMock()

from api.main import app, get_db

client = TestClient(app)
VALID_KEY = "dev_secret_key_change_me"


def test_pagination_defaults():
    """
    Test: Does the /people endpoint enforce pagination limits?
    """
    # Mock DB query
    mock_query = MagicMock()
    mock_query.count.return_value = 100
    mock_query.filter.return_value = mock_query
    mock_query.order_by.return_value.limit.return_value.offset.return_value.all.return_value = []
    
    mock_db = MagicMock()
    mock_db.query.return_value = mock_query
    
    app.dependency_overrides[get_db] = lambda: mock_db
    
    try:
        # 1. Default limit (should be 50)
        client.get("/people")
        mock_query.order_by.return_value.limit.assert_called_with(50)
        
        # 2. Custom limit (should respect valid value)
        client.get("/people?limit=10")
        mock_query.order_by.return_value.limit.assert_called_with(10)
        
        # 3. Invalid limit (should default or error, FastAPI handles validation)
        response = client.get("/people?limit=1000")
        # FastAPI validation error
        assert response.status_code == 422 
        
    finally:
        del app.dependency_overrides[get_db]

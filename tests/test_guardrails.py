import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock
import sys
import os

# Setup mocks for heavy dependencies
sys.modules["llama_cpp"] = MagicMock()
sys.modules["redis"] = MagicMock()
# Do NOT mock celery here, let it load or patch specifically if needed.

from api.main import app, get_db

client = TestClient(app)
VALID_KEY = "dev_secret_key_change_me"

def test_date_validation():
    """
    Test: Does the API reject malformed dates?
    """
    response = client.get("/search?q=zoning&date_from=invalid-date")
    assert response.status_code == 400
    assert "YYYY-MM-DD" in response.json()["detail"]

def test_deep_health_check(mocker):
    """
    Test: Does /health fail if the DB is down?
    """
    # Mock DB failure
    mock_db = MagicMock()
    mock_db.execute.side_effect = Exception("DB Down")
    
    app.dependency_overrides[get_db] = lambda: mock_db
    
    response = client.get("/health")
    # Note: We expect 503 if we implement the health check logic correctly.
    # Currently /health might not be implemented in main.py yet, so this verifies the RED aspect.
    if response.status_code == 404:
        pytest.fail("Health endpoint not implemented yet")
        
    assert response.status_code == 503
    assert "Database unreachable" in response.json()["detail"]
    
    del app.dependency_overrides[get_db]

def test_db_length_constraint():
    """
    Test: Does the DB schema enforce length limits?
    """
    from pipeline.models import Person
    # Verify the 'name' column has a length of 255
    assert Person.name.type.length == 255
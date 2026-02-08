import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import sys
import os
from unittest.mock import MagicMock

# Add the project root to the path
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(root_dir)
sys.path.append(os.path.join(root_dir, 'api'))

# Mock heavy AI dependency before importing api.main
sys.modules["llama_cpp"] = MagicMock()

from api.main import app, get_db
from pipeline.models import Base, Event, Place, Organization

client = TestClient(app)

# Use a thread-safe in-memory SQLite DB for FastAPI TestClient worker threads.
engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autoflush=False, autocommit=False, bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture
def client_with_db():
    """Inject per-test in-memory DB session dependency for API tests."""
    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_db] = override_get_db
    yield client
    Base.metadata.drop_all(bind=engine)
    app.dependency_overrides.pop(get_db, None)

@pytest.fixture(autouse=True)
def clear_overrides():
    """Ensure dependency overrides don't leak between tests."""
    yield
    app.dependency_overrides.pop(get_db, None)

# SECURITY: Test Keys
VALID_KEY = "dev_secret_key_change_me"

def test_report_issue_success(client_with_db):
    """
    Test: Can a user successfully report a broken link with a valid API key?
    """
    # 1. Setup: Add a dummy meeting to the database so we have something to report.
    # Need a Place and Organization first due to foreign keys
    place = Place(name="Test City", ocd_division_id="ocd-test", state="CA")
    db = TestingSessionLocal()
    db.add(place)
    db.commit()
    
    org = Organization(name="City Council", place_id=place.id, ocd_id="ocd-org/1")
    db.add(org)
    db.commit()

    event = Event(id=123, name="Test Meeting", ocd_division_id="ocd-test", organization_id=org.id, place_id=place.id)
    db.add(event)
    db.commit()
    db.close()

    # 2. Action: Send a POST request to the API with the KEY
    report_data = {
        "event_id": 123,
        "issue_type": "broken_link",
        "description": "The agenda PDF is returning a 404 error."
    }
    response = client_with_db.post("/report-issue", json=report_data, headers={"X-API-Key": VALID_KEY})

    # 3. Verify: Did the API return success?
    assert response.status_code == 200
    assert response.json()["status"] == "success"

def test_report_issue_unauthorized(client_with_db):
    """
    Test: Does the API reject requests without a key?
    """
    response = client_with_db.post("/report-issue", json={"event_id": 1, "issue_type": "other"})
    assert response.status_code == 401
    assert "Invalid or missing API Key" in response.json()["detail"]

def test_report_issue_invalid_event(client_with_db):
    """
    Test: Does the API correctly reject reports for meetings that don't exist?
    """
    report_data = {
        "event_id": 9999, # This ID does not exist
        "issue_type": "broken_link"
    }
    response = client_with_db.post("/report-issue", json=report_data, headers={"X-API-Key": VALID_KEY})
    
    # Verify: 404 Not Found
    assert response.status_code == 404
    assert "Meeting not found" in response.json()["detail"]

def test_report_issue_invalid_type(client_with_db):
    """
    Test: Does the API reject invalid issue types (like 'fake_issue')?
    """
    # 1. Setup: Add a valid event
    place = Place(name="Test City", ocd_division_id="ocd-test", state="CA")
    db = TestingSessionLocal()
    db.add(place)
    db.commit()
    event = Event(id=1, name="Test", ocd_division_id="ocd-test", place_id=place.id)
    db.add(event)
    db.commit()
    db.close()

    # 2. Action: Send bad issue type
    report_data = {
        "event_id": 1,
        "issue_type": "completely_made_up_issue"
    }
    response = client_with_db.post("/report-issue", json=report_data, headers={"X-API-Key": VALID_KEY})
    
    # Verify: 400 Bad Request
    assert response.status_code == 400
    assert "Invalid issue_type" in response.json()["detail"]

def test_report_issue_input_validation(client_with_db):
    """
    Test: Does Pydantic catch missing fields?
    """
    # Action: Missing 'issue_type'
    response = client_with_db.post("/report-issue", json={"event_id": 1}, headers={"X-API-Key": VALID_KEY})
    
    # Verify: 422 Unprocessable Entity (FastAPI's default for validation errors)
    assert response.status_code == 422

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import sys
import os

# Add the project root to the path
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(root_dir)
sys.path.append(os.path.join(root_dir, 'api'))

from api.main import app, get_db
from pipeline.models import Base, Event, DataIssue, IssueType, Place, Organization, Membership, Person, Document, Catalog, AgendaItem, create_tables

from sqlalchemy.pool import StaticPool

# 1. Setup: Create a temporary, in-memory database for testing the API.
# StaticPool ensures all connections use the same in-memory database.
engine = create_engine(
    'sqlite:///:memory:', 
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autoflush=False, autocommit=False, bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

# We 'inject' our testing database into the real app.
app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    """Creates the tables before every test and clears them after."""
    create_tables(engine)
    yield
    Base.metadata.drop_all(bind=engine)

# SECURITY: Test Keys
VALID_KEY = "dev_secret_key_change_me"

def test_report_issue_success(monkeypatch):
    """
    Test: Can a user successfully report a broken link with a valid API key?
    """
    # 1. Setup: Add a dummy meeting to the database so we have something to report.
    db = TestingSessionLocal()
    
    # Need a Place and Organization first due to foreign keys
    place = Place(name="Test City", ocd_division_id="ocd-test", state="CA")
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
    response = client.post("/report-issue", json=report_data, headers={"X-API-Key": VALID_KEY})

    # 3. Verify: Did the API return success?
    assert response.status_code == 200
    assert response.json()["status"] == "success"

def test_report_issue_unauthorized():
    """
    Test: Does the API reject requests without a key?
    """
    response = client.post("/report-issue", json={"event_id": 1, "issue_type": "other"})
    assert response.status_code == 401
    assert "Invalid or missing API Key" in response.json()["detail"]

def test_report_issue_invalid_event():
    """
    Test: Does the API correctly reject reports for meetings that don't exist?
    """
    report_data = {
        "event_id": 9999, # This ID does not exist
        "issue_type": "broken_link"
    }
    response = client.post("/report-issue", json=report_data, headers={"X-API-Key": VALID_KEY})
    
    # Verify: 404 Not Found
    assert response.status_code == 404
    assert "Meeting not found" in response.json()["detail"]

def test_report_issue_invalid_type():
    """
    Test: Does the API reject invalid issue types (like 'fake_issue')?
    """
    # 1. Setup: Add a valid event
    db = TestingSessionLocal()
    place = Place(name="Test City", ocd_division_id="ocd-test", state="CA")
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
    response = client.post("/report-issue", json=report_data, headers={"X-API-Key": VALID_KEY})
    
    # Verify: 400 Bad Request
    assert response.status_code == 400
    assert "Invalid issue_type" in response.json()["detail"]

def test_report_issue_input_validation():
    """
    Test: Does Pydantic catch missing fields?
    """
    # Action: Missing 'issue_type'
    response = client.post("/report-issue", json={"event_id": 1}, headers={"X-API-Key": VALID_KEY})
    
    # Verify: 422 Unprocessable Entity (FastAPI's default for validation errors)
    assert response.status_code == 422

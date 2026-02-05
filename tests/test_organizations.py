import pytest
import sys
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Setup path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from pipeline.models import Base, Place, Organization, Event

@pytest.fixture
def db_session():
    """Creates a temporary in-memory database for testing relationships."""
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def test_organization_hierarchy(db_session):
    """
    Test: Does the OCD hierarchy work?
    Place (City) -> Organization (Body) -> Event (Meeting)
    """
    # 1. Create a City
    berkeley = Place(name="Berkeley", ocd_division_id="ocd-berkeley")
    db_session.add(berkeley)
    db_session.flush()

    # 2. Create an Organization within that City
    council = Organization(
        name="City Council", 
        classification="legislature", 
        place_id=berkeley.id
    )
    db_session.add(council)
    db_session.flush()

    # 3. Create a Meeting held by that Organization
    meeting = Event(
        name="Regular Meeting", 
        place_id=berkeley.id, 
        organization_id=council.id
    )
    db_session.add(meeting)
    db_session.commit()

    # 4. Verify Relationships
    # Can we find the city from the meeting?
    assert meeting.place.name == "Berkeley"
    # Can we find the organization from the meeting?
    assert meeting.organization.name == "City Council"
    # Can we see all meetings for this council?
    assert len(council.events) == 1
    assert council.events[0].name == "Regular Meeting"

def test_organization_deduplication(db_session):
    """
    Test: Does the system correctly link multiple meetings to the SAME organization?
    """
    place = Place(name="Dublin", ocd_division_id="ocd-dublin")
    db_session.add(place)
    db_session.flush()

    org = Organization(name="City Council", place_id=place.id)
    db_session.add(org)
    db_session.flush()

    # Add two meetings
    m1 = Event(name="Jan Meeting", place_id=place.id, organization_id=org.id)
    m2 = Event(name="Feb Meeting", place_id=place.id, organization_id=org.id)
    db_session.add_all([m1, m2])
    db_session.commit()

    assert len(org.events) == 2

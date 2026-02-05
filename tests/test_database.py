import sys
import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add project root and pipeline dir to path
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(root_dir)
sys.path.append(os.path.join(root_dir, 'pipeline'))

from pipeline.models import DeclarativeBase, Place, Event, EventStage
from pipeline.promote_stage import promote_stage

@pytest.fixture
def db_session():
    """Sets up an in-memory SQLite database for testing."""
    engine = create_engine('sqlite:///:memory:')
    DeclarativeBase.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def test_place_creation(db_session):
    """Verify that we can create and retrieve city records."""
    new_place = Place(
        name="Test City",
        ocd_division_id="ocd-division/test",
        state="CA"
    )
    db_session.add(new_place)
    db_session.commit()
    
    retrieved = db_session.query(Place).filter_by(name="Test City").first()
    assert retrieved is not None
    assert retrieved.state == "CA"

def test_promotion_logic(db_session, mocker):
    """
    Verify that promote_stage correctly moves data from staging to production.
    We mock the db_connect in promote_stage to use our in-memory engine.
    """
    # 1. Setup mock city
    place = Place(name="Belmont", ocd_division_id="ocd-belmont")
    db_session.add(place)
    
    # 2. Add a staged event
    staged = EventStage(
        name="Council Meeting",
        ocd_division_id="ocd-belmont",
        record_date=None # Using default
    )
    db_session.add(staged)
    db_session.commit()
    
    # 3. Mock the database connection in promote_stage
    mocker.patch('pipeline.promote_stage.db_connect', return_value=db_session.get_bind())
    
    # 4. Run promotion
    promote_stage()
    
    # 5. Verify results
    # Should now be in Event table
    event = db_session.query(Event).filter_by(name="Council Meeting").first()
    assert event is not None
    assert event.place_id == place.id
    
    # Should be cleared from EventStage
    staged_count = db_session.query(EventStage).count()
    assert staged_count == 0

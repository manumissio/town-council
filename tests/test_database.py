import importlib
import sys
import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Setup: Add project root and pipeline dir to path so imports work.
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(root_dir)
sys.path.append(os.path.join(root_dir, 'pipeline'))

from pipeline.models import Base, Place, Event, EventStage
from pipeline.promote_stage import promote_stage

@pytest.fixture
def db_session():
    """
    Setup: This creates a temporary, empty database in memory for each test.
    This ensures that one test doesn't mess up another test's data.
    """
    # ':memory:' means the database exists only in RAM and disappears after the test.
    engine = create_engine('sqlite:///:memory:')
    # Create all the tables (Place, Event, etc.) in this temporary DB.
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session # This provides the 'session' to the test function.
    session.close() # Cleanup after the test finishes.

def test_place_creation(db_session):
    """
    Test: Can we save and load a City (Place) from the database?
    """
    # 1. Create a dummy city.
    new_place = Place(
        name="Test City",
        ocd_division_id="ocd-division/test",
        state="CA"
    )
    # 2. Add it to the DB and save (commit).
    db_session.add(new_place)
    db_session.commit()
    
    # 3. Try to find it again.
    retrieved = db_session.query(Place).filter_by(name="Test City").first()
    assert retrieved is not None
    assert retrieved.state == "CA"

def test_promotion_logic(db_session, mocker):
    """
    Test: Does the 'promotion' logic move data correctly?
    We want to ensure that a meeting in 'EventStage' moves to the 'Event' table.
    """
    # 1. Setup: Create a city first (needed for the foreign key link).
    place = Place(name="Belmont", ocd_division_id="ocd-belmont", state="CA")
    db_session.add(place)
    
    # 2. Add a meeting to the 'Staging' area (EventStage).
    staged = EventStage(
        name="Council Meeting",
        ocd_division_id="ocd-belmont",
        record_date=None # Will use today's date by default.
    )
    db_session.add(staged)
    db_session.commit()
    
    # 3. Mock: We 'trick' the promote_stage function into using our temporary DB
    # instead of the real Postgres database.
    mocker.patch('pipeline.promote_stage.db_connect', return_value=db_session.get_bind())
    
    # 4. Action: Run the promotion script.
    promote_stage()
    
    # 5. Verify: Did the meeting move?
    # It should now exist in the main 'Event' table.
    event = db_session.query(Event).filter_by(name="Council Meeting").first()
    assert event is not None
    assert event.place_id == place.id
    
    # And it should have been deleted from the 'Staging' table.
    staged_count = db_session.query(EventStage).count()
    assert staged_count == 0


def test_promotion_keeps_blocked_rows_in_event_stage(db_session, mocker):
    place = Place(name="Belmont", ocd_division_id="ocd-belmont", state="CA")
    db_session.add(place)
    db_session.add_all(
        [
            EventStage(name="Council Meeting", ocd_division_id="ocd-belmont"),
            EventStage(name="Blocked Meeting", ocd_division_id="ocd-missing"),
        ]
    )
    db_session.commit()

    mocker.patch('pipeline.promote_stage.db_connect', return_value=db_session.get_bind())

    promote_stage()

    assert db_session.query(Event).filter_by(name="Council Meeting").count() == 1
    remaining = db_session.query(EventStage).all()
    assert len(remaining) == 1
    assert remaining[0].name == "Blocked Meeting"


def test_db_connect_requires_explicit_database_url(monkeypatch):
    import pipeline.models as models

    monkeypatch.delenv("DATABASE_URL", raising=False)
    models = importlib.reload(models)

    with pytest.raises(RuntimeError, match="DATABASE_URL is not set"):
        models.db_connect()


def test_db_connect_uses_postgresql_pooling(monkeypatch, mocker):
    import pipeline.models as models

    database_url = "postgresql://town-council:test@localhost/town_council"
    monkeypatch.setenv("DATABASE_URL", database_url)
    models = importlib.reload(models)
    create_engine_mock = mocker.patch.object(models, "create_engine", autospec=True)

    models.db_connect()

    create_engine_mock.assert_called_once_with(
        database_url,
        pool_size=10,
        max_overflow=20,
        pool_timeout=30,
        pool_recycle=1800,
    )


def test_db_connect_allows_explicit_sqlite_url_without_fallback_pooling(monkeypatch, mocker):
    import pipeline.models as models

    database_url = "sqlite:///:memory:"
    monkeypatch.setenv("DATABASE_URL", database_url)
    models = importlib.reload(models)
    create_engine_mock = mocker.patch.object(models, "create_engine", autospec=True)

    models.db_connect()

    create_engine_mock.assert_called_once_with(database_url)

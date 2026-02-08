import pytest
import sys
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# We use a shared in-memory database so multiple connections can see the same tables.
# This is critical because workers create their own engines.
TEST_DB_URL = "sqlite:///file:testdb?mode=memory&cache=shared"

@pytest.fixture(scope="session", autouse=True)
def shared_engine():
    """
    Creates a single engine for the entire test session.
    """
    from pipeline.models import (
        Base, Place, Organization, Event, Document, 
        Catalog, AgendaItem, DataIssue, EventStage
    )
    # The URI must have the same name for all engines to share the DB
    engine = create_engine(TEST_DB_URL)
    Base.metadata.create_all(engine)
    return engine

@pytest.fixture(autouse=True)
def mock_db_connect(monkeypatch, shared_engine):
    """
    Monkeypatch ALL workers to use the shared test database.
    """
    monkeypatch.setenv("DATABASE_URL", TEST_DB_URL)
    
    # We patch db_connect in multiple modules where it might be imported
    targets = [
        "pipeline.models.db_connect",
        "pipeline.agenda_worker.db_connect",
        "pipeline.summarizer.db_connect",
        "pipeline.topic_worker.db_connect",
        "pipeline.similarity_worker.db_connect",
        "pipeline.nlp_worker.db_connect",
        "pipeline.promote_stage.db_connect",
        "pipeline.downloader.db_connect",
        "api.main.db_connect"
    ]
    for target in targets:
        try:
            monkeypatch.setattr(target, lambda: shared_engine)
        except (AttributeError, ImportError):
            pass
    yield

@pytest.fixture(autouse=True)
def reset_nlp_cache():
    """
    Prevents Mock Pollution: Clears the global NLP model cache before every test.
    """
    import pipeline.nlp_worker
    pipeline.nlp_worker._cached_nlp = None
    yield

@pytest.fixture
def db_session(shared_engine):
    """
    Setup: Returns a session tied to the shared test database.
    We clear the data between tests but keep the tables.
    """
    from pipeline.models import Base
    Session = sessionmaker(bind=shared_engine)
    session = Session()
    
    yield session
    
    # Clean up data after every test to ensure isolation
    session.rollback()
    for table in reversed(Base.metadata.sorted_tables):
        session.execute(table.delete())
    session.commit()
    session.close()

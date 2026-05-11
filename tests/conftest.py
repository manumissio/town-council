import pytest
import sys
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


OPTIONAL_NLP_IMPORT_ERRORS = (ImportError, ModuleNotFoundError, OSError, RuntimeError)

# Use a process-unique shared in-memory database:
# - shared within one pytest process (workers create their own engines)
# - isolated across concurrent pytest processes (avoids DDL races on drop/create)
# This fixture is intentionally SQLite because most tests exercise backend-
# agnostic behavior rather than the PostgreSQL runtime contract.
TEST_DB_URL = f"sqlite:///file:tc_testdb_{os.getpid()}?mode=memory&cache=shared&uri=true"

# Test collection can import app modules that initialize DB engines immediately.
# Pytest owns this value so collection never touches a developer's real DB.
os.environ["DATABASE_URL"] = TEST_DB_URL

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

    # Force drop all existing tables to ensure clean schema
    # This prevents issues with cached table definitions from previous test runs
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()

@pytest.fixture(autouse=True)
def mock_db_connect(monkeypatch, shared_engine):
    """
    Keep test DB ownership centralized without weakening runtime DB contracts.
    """
    monkeypatch.setenv("DATABASE_URL", TEST_DB_URL)
    import pipeline.db_session as db_session_module

    db_session_module._SessionLocal = None
    
    # Patch DB factory seams proven by tests; direct db_session imports use this module.
    targets = [
        "pipeline.models.db_connect",
        "pipeline.agenda_worker.db_connect",
        "pipeline.topic_worker.db_connect",
        "pipeline.nlp_worker.db_connect",
        "pipeline.promote_stage.db_connect",
        "pipeline.downloader.db_connect",
        "api.app_setup.db_connect",
        "api.main.db_connect"
    ]
    for target in targets:
        try:
            monkeypatch.setattr(target, lambda: shared_engine, raising=False)
        except OPTIONAL_NLP_IMPORT_ERRORS:
            # Some optional modules (for example spaCy stack on Py3.14) can fail
            # during import; skip patching those modules so other tests still run.
            pass
    try:
        import api.app_setup as app_setup

        app_setup.SessionLocal = None
        app_setup._db_init_error = None
    except OPTIONAL_NLP_IMPORT_ERRORS:
        pass
    yield
    db_session_module._SessionLocal = None


@pytest.fixture(autouse=True)
def reset_api_test_state():
    """
    Prevent API dependency overrides and rate-limit counters from leaking.
    """
    def _reset_state() -> None:
        api_main = sys.modules.get("api.main")
        if api_main is None:
            return
        app = getattr(api_main, "app", None)
        if app is not None:
            app.dependency_overrides.clear()
            limiter = getattr(getattr(app, "state", None), "limiter", None)
            reset = getattr(limiter, "reset", None)
            if callable(reset):
                reset()
            storage = getattr(getattr(limiter, "limiter", None), "storage", None)
            storage_reset = getattr(storage, "reset", None)
            if callable(storage_reset):
                storage_reset()

    _reset_state()
    yield
    _reset_state()

@pytest.fixture(autouse=True)
def reset_nlp_cache():
    """
    Prevents Mock Pollution: Clears the global NLP model cache before every test.
    """
    try:
        import pipeline.nlp_worker
        pipeline.nlp_worker._cached_nlp = None
    except OPTIONAL_NLP_IMPORT_ERRORS:
        # Some environments cannot import spaCy-dependent modules.
        # In that case we skip NLP cache reset and let non-NLP tests run.
        pass
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

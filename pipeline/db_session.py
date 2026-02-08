"""
Database Session Context Manager

What's a context manager?
--------------------------
A context manager is a Python pattern that automatically handles setup and cleanup.
You use it with the "with" keyword, like this:

    with db_session() as session:
        # Do database work here
        session.commit()
    # Session is automatically closed when the "with" block ends

Why is this better than manual session management?
---------------------------------------------------
BEFORE (manual):
    engine = db_connect()
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        # work...
        session.commit()
    except Exception as e:
        session.rollback()
    finally:
        session.close()

AFTER (context manager):
    with db_session() as session:
        # work...
        session.commit()

Benefits:
1. Less code duplication (this pattern was repeated 55+ times!)
2. Guaranteed cleanup (session always closes, even if errors occur)
3. Easier to read and understand
4. Harder to forget error handling

This file is imported by all workers to ensure consistent database access.
"""

from contextlib import contextmanager
from sqlalchemy.orm import sessionmaker
from pipeline.models import db_connect

# Create a session factory that we'll reuse
# This connects to the database once and creates sessions from that connection
_SessionLocal = None

def _get_session_factory():
    """
    Creates or returns the session factory.

    What's a factory?
    A factory is an object that creates other objects. In this case, it creates
    database sessions. We only want to create it once and reuse it.
    """
    global _SessionLocal
    if _SessionLocal is None:
        engine = db_connect()
        _SessionLocal = sessionmaker(bind=engine)
    return _SessionLocal


@contextmanager
def db_session():
    """
    Context manager for database sessions with automatic cleanup.

    Usage:
        with db_session() as session:
            # Do your database work here
            user = session.query(User).first()
            session.commit()
        # Session automatically closed when you exit the "with" block

    What happens under the hood:
    1. Creates a new database session
    2. Yields it to your code (the "as session" part)
    3. If an error occurs, rolls back any uncommitted changes
    4. Always closes the session, no matter what

    Why rollback on error?
    If you made changes but didn't commit, and then an error happened,
    we need to "undo" those changes so the database stays consistent.
    Think of it like pressing Ctrl+Z after making a mistake.
    """
    SessionLocal = _get_session_factory()
    session = SessionLocal()

    try:
        # Yield gives control back to your code
        # Everything after "with db_session() as session:" runs here
        yield session

    except Exception:
        # If ANY error occurred, undo uncommitted changes
        # This keeps the database in a consistent state
        session.rollback()
        raise  # Re-raise the exception so your code knows something failed

    finally:
        # ALWAYS close the session when done, no matter what happened
        # This prevents "connection leaks" where we run out of database connections
        session.close()

"""Shared SQLAlchemy session helper used across pipeline workers."""

from contextlib import contextmanager
from sqlalchemy.orm import sessionmaker
from pipeline.models import db_connect

_SessionLocal = None

def _get_session_factory():
    """Create the session factory once, then reuse it."""
    global _SessionLocal
    if _SessionLocal is None:
        engine = db_connect()
        _SessionLocal = sessionmaker(bind=engine)
    return _SessionLocal


@contextmanager
def db_session():
    """Yield a DB session, rollback on error, and always close it."""
    SessionLocal = _get_session_factory()
    session = SessionLocal()

    try:
        yield session

    except Exception:
        # Roll back for any failure, including app-level errors.
        session.rollback()
        raise

    finally:
        session.close()

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Final

from sqlalchemy.engine import Engine

from pipeline.model_base import Base


POSTGRESQL_SCHEME: Final = "postgresql"
POSTGRESQL_POOL_SIZE: Final = 10
POSTGRESQL_MAX_OVERFLOW: Final = 20
POSTGRESQL_POOL_TIMEOUT: Final = 30
POSTGRESQL_POOL_RECYCLE_SECONDS: Final = 1800
DATABASE_URL_ENV_VAR: Final = "DATABASE_URL"
DATABASE_URL_MISSING_ERROR: Final = "DATABASE_URL is not set. Configure it explicitly for runtime or tests."

CreateEngineCallable = Callable[..., Engine]


def db_connect_with(create_engine_callable: CreateEngineCallable) -> Engine:
    """
    Build a SQLAlchemy engine from the explicit DATABASE_URL contract.

    Runtime stays PostgreSQL-first and fails fast when DATABASE_URL is unset.
    Tests and ad hoc tooling may still pass an explicit SQLite URL when they
    intentionally need a lightweight fixture database.
    """
    database_url = os.getenv(DATABASE_URL_ENV_VAR)

    if database_url and database_url.startswith(POSTGRESQL_SCHEME):
        return create_engine_callable(
            database_url,
            pool_size=POSTGRESQL_POOL_SIZE,
            max_overflow=POSTGRESQL_MAX_OVERFLOW,
            pool_timeout=POSTGRESQL_POOL_TIMEOUT,
            pool_recycle=POSTGRESQL_POOL_RECYCLE_SECONDS,
            pool_pre_ping=True,
        )
    if database_url:
        return create_engine_callable(database_url)
    raise RuntimeError(DATABASE_URL_MISSING_ERROR)


def create_tables(engine: Engine) -> None:
    Base.metadata.create_all(engine)

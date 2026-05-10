"""
Additive schema migrations for local/dev environments.

Why this exists:
This repo does not use Alembic migrations yet. `create_all()` can create missing
tables, but it will NOT add new columns to existing tables. When the Python
models evolve, older databases can break at runtime.

This script applies small, additive migrations (safe ALTER TABLE) so existing
dev databases can keep working without requiring destructive resets.
"""

from __future__ import annotations

import logging

from sqlalchemy.engine import Connection

from pipeline import migrate_v8
from pipeline import migrate_v9
from pipeline.db_migration_columns import add_column_if_missing, postgres_column_exists
from pipeline.db_migration_runner import run_migrations
from pipeline.models import db_connect

logger = logging.getLogger("db-migrate")


def _postgres_column_exists(conn: Connection, table: str, column: str) -> bool:
    return postgres_column_exists(conn, table, column)


def _add_column_if_missing(conn: Connection, table: str, column: str, ddl: str) -> bool:
    return add_column_if_missing(conn, table, column, ddl, logger)


def migrate() -> None:
    run_migrations(
        db_connect_callable=db_connect,
        migrate_v8_module=migrate_v8,
        migrate_v9_module=migrate_v9,
        logger=logger,
    )


if __name__ == "__main__":
    migrate()

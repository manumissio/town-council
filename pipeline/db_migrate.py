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
from sqlalchemy import text

from pipeline.models import db_connect
from pipeline import migrate_v8

logger = logging.getLogger("db-migrate")


def _postgres_column_exists(conn, table: str, column: str) -> bool:
    return (
        conn.execute(
            text(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = :table
                  AND column_name = :column
                LIMIT 1
                """
            ),
            {"table": table, "column": column},
        ).scalar()
        is not None
    )


def migrate() -> None:
    engine = db_connect()
    with engine.begin() as conn:
        if engine.dialect.name != "postgresql":
            # SQLite is commonly used in tests and local scripts. We only apply
            # additive migrations for Postgres here.
            return

        # Minimal set of additive migrations required by the current codebase.
        # These are safe to run multiple times.
        if not _postgres_column_exists(conn, "person", "person_type"):
            conn.execute(
                text(
                    "ALTER TABLE person ADD COLUMN person_type VARCHAR(20) NOT NULL DEFAULT 'mentioned'"
                )
            )
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_person_person_type ON person (person_type)"))

        # Agenda segmentation status columns (additive; safe to run repeatedly).
        if not _postgres_column_exists(conn, "catalog", "agenda_segmentation_status"):
            conn.execute(
                text("ALTER TABLE catalog ADD COLUMN agenda_segmentation_status VARCHAR(20)")
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_catalog_agenda_segmentation_status "
                    "ON catalog (agenda_segmentation_status)"
                )
            )
        if not _postgres_column_exists(conn, "catalog", "agenda_segmentation_attempted_at"):
            conn.execute(
                text("ALTER TABLE catalog ADD COLUMN agenda_segmentation_attempted_at TIMESTAMP")
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_catalog_agenda_segmentation_attempted_at "
                    "ON catalog (agenda_segmentation_attempted_at)"
                )
            )
        if not _postgres_column_exists(conn, "catalog", "agenda_segmentation_item_count"):
            conn.execute(
                text("ALTER TABLE catalog ADD COLUMN agenda_segmentation_item_count INTEGER")
            )
        if not _postgres_column_exists(conn, "catalog", "agenda_segmentation_error"):
            conn.execute(
                text("ALTER TABLE catalog ADD COLUMN agenda_segmentation_error TEXT")
            )

    # Milestone B2 (pgvector backend): run dedicated migration with strict ordering.
    try:
        migrate_v8.migrate()
    except Exception as exc:
        # Keep core additive migrations available even when pgvector is not active.
        logger.warning("migrate_v8 skipped: %s", exc)


if __name__ == "__main__":
    migrate()

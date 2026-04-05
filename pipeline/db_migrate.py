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
from pipeline import migrate_v9

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


def _add_column_if_missing(conn, table: str, column: str, ddl: str) -> bool:
    if _postgres_column_exists(conn, table, column):
        logger.info("migration_skip table=%s column=%s reason=already_present", table, column)
        return False
    conn.execute(text(ddl))
    logger.info("migration_apply table=%s column=%s", table, column)
    return True


def migrate() -> None:
    engine = db_connect()
    with engine.begin() as conn:
        if engine.dialect.name != "postgresql":
            # SQLite remains useful for tests and explicit ad hoc scripts, but
            # additive runtime migrations only target PostgreSQL databases.
            return

        # Keep db_migrate as the one supported upgrade entrypoint, even for
        # older columns that originally landed through one-off versioned scripts.
        _add_column_if_missing(
            conn,
            "event",
            "organization_id",
            "ALTER TABLE event ADD COLUMN organization_id INTEGER REFERENCES organization(id)",
        )
        _add_column_if_missing(
            conn,
            "event_stage",
            "organization_name",
            "ALTER TABLE event_stage ADD COLUMN organization_name VARCHAR(255)",
        )
        _add_column_if_missing(
            conn,
            "catalog",
            "related_ids",
            "ALTER TABLE catalog ADD COLUMN related_ids JSON",
        )
        _add_column_if_missing(
            conn,
            "place",
            "legistar_client",
            "ALTER TABLE place ADD COLUMN legistar_client VARCHAR(100)",
        )
        if _add_column_if_missing(
            conn,
            "person",
            "is_elected",
            "ALTER TABLE person ADD COLUMN is_elected BOOLEAN DEFAULT FALSE",
        ):
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_person_is_elected ON person (is_elected)"))
        if _add_column_if_missing(
            conn,
            "person",
            "person_type",
            "ALTER TABLE person ADD COLUMN person_type VARCHAR(20) NOT NULL DEFAULT 'mentioned'",
        ):
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_person_person_type ON person (person_type)"))

        _add_column_if_missing(
            conn,
            "catalog",
            "content_hash",
            "ALTER TABLE catalog ADD COLUMN content_hash VARCHAR(64)",
        )
        _add_column_if_missing(
            conn,
            "catalog",
            "summary_source_hash",
            "ALTER TABLE catalog ADD COLUMN summary_source_hash VARCHAR(64)",
        )
        _add_column_if_missing(
            conn,
            "catalog",
            "topics_source_hash",
            "ALTER TABLE catalog ADD COLUMN topics_source_hash VARCHAR(64)",
        )

        _add_column_if_missing(
            conn,
            "agenda_item",
            "page_number",
            "ALTER TABLE agenda_item ADD COLUMN page_number INTEGER",
        )
        _add_column_if_missing(
            conn,
            "agenda_item",
            "text_offset",
            "ALTER TABLE agenda_item ADD COLUMN text_offset INTEGER",
        )
        _add_column_if_missing(
            conn,
            "agenda_item",
            "votes",
            "ALTER TABLE agenda_item ADD COLUMN votes JSON",
        )
        _add_column_if_missing(
            conn,
            "agenda_item",
            "raw_history",
            "ALTER TABLE agenda_item ADD COLUMN raw_history TEXT",
        )
        if _add_column_if_missing(
            conn,
            "agenda_item",
            "legistar_matter_id",
            "ALTER TABLE agenda_item ADD COLUMN legistar_matter_id INTEGER",
        ):
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_agenda_item_legistar_matter_id "
                    "ON agenda_item (legistar_matter_id)"
                )
            )
        _add_column_if_missing(
            conn,
            "agenda_item",
            "spatial_coords",
            "ALTER TABLE agenda_item ADD COLUMN spatial_coords JSON",
        )

        # Agenda segmentation status columns (additive; safe to run repeatedly).
        if _add_column_if_missing(
            conn,
            "catalog",
            "agenda_segmentation_status",
            "ALTER TABLE catalog ADD COLUMN agenda_segmentation_status VARCHAR(20)",
        ):
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_catalog_agenda_segmentation_status "
                    "ON catalog (agenda_segmentation_status)"
                )
            )
        if _add_column_if_missing(
            conn,
            "catalog",
            "agenda_segmentation_attempted_at",
            "ALTER TABLE catalog ADD COLUMN agenda_segmentation_attempted_at TIMESTAMP",
        ):
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_catalog_agenda_segmentation_attempted_at "
                    "ON catalog (agenda_segmentation_attempted_at)"
                )
            )
        _add_column_if_missing(
            conn,
            "catalog",
            "agenda_segmentation_item_count",
            "ALTER TABLE catalog ADD COLUMN agenda_segmentation_item_count INTEGER",
        )
        _add_column_if_missing(
            conn,
            "catalog",
            "agenda_segmentation_error",
            "ALTER TABLE catalog ADD COLUMN agenda_segmentation_error TEXT",
        )

        if _add_column_if_missing(
            conn,
            "catalog",
            "extraction_status",
            "ALTER TABLE catalog ADD COLUMN extraction_status VARCHAR(20)",
        ):
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_catalog_extraction_status "
                    "ON catalog (extraction_status)"
                )
            )
        if _add_column_if_missing(
            conn,
            "catalog",
            "extraction_attempted_at",
            "ALTER TABLE catalog ADD COLUMN extraction_attempted_at TIMESTAMP",
        ):
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_catalog_extraction_attempted_at "
                    "ON catalog (extraction_attempted_at)"
                )
            )
        _add_column_if_missing(
            conn,
            "catalog",
            "extraction_attempt_count",
            "ALTER TABLE catalog ADD COLUMN extraction_attempt_count INTEGER",
        )
        _add_column_if_missing(
            conn,
            "catalog",
            "extraction_error",
            "ALTER TABLE catalog ADD COLUMN extraction_error TEXT",
        )
        _add_column_if_missing(
            conn,
            "catalog",
            "entities_source_hash",
            "ALTER TABLE catalog ADD COLUMN entities_source_hash VARCHAR(64)",
        )
        _add_column_if_missing(
            conn,
            "catalog",
            "agenda_items_hash",
            "ALTER TABLE catalog ADD COLUMN agenda_items_hash VARCHAR(64)",
        )

        conn.execute(
            text(
                """
                UPDATE catalog
                SET extraction_status = CASE
                    WHEN content IS NOT NULL AND btrim(content) <> '' THEN 'complete'
                    ELSE 'pending'
                END
                WHERE extraction_status IS NULL
                """
            )
        )
        conn.execute(
            text(
                """
                UPDATE catalog
                SET extraction_attempt_count = COALESCE(extraction_attempt_count, 0)
                WHERE extraction_attempt_count IS NULL
                """
            )
        )
        # Older databases may have the person_type column but still need the
        # original conservative backfill so official-only views stay stable.
        conn.execute(
            text(
                """
                UPDATE person
                SET person_type = 'mentioned'
                WHERE person_type IS NULL OR person_type = ''
                """
            )
        )
        conn.execute(
            text(
                """
                UPDATE person
                SET person_type = 'official'
                WHERE is_elected = TRUE
                   OR lower(coalesce(current_role, '')) LIKE '%mayor%'
                   OR lower(coalesce(current_role, '')) LIKE '%council%'
                   OR lower(coalesce(current_role, '')) LIKE '%commissioner%'
                   OR id IN (SELECT person_id FROM membership)
                """
            )
        )

    # Milestone B2 (pgvector backend): run dedicated migration with strict ordering.
    try:
        migrate_v8.migrate()
    except Exception as exc:
        # Keep core additive migrations available even when pgvector is not active.
        logger.warning("migrate_v8 skipped: %s", exc)

    # Milestone C lineage columns.
    try:
        migrate_v9.migrate()
    except Exception as exc:
        logger.warning("migrate_v9 skipped: %s", exc)


if __name__ == "__main__":
    migrate()

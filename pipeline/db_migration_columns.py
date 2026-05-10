from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.engine import Connection


@dataclass(frozen=True)
class ColumnMigration:
    table: str
    column: str
    ddl: str
    index_sql: str | None = None


CORE_COLUMN_MIGRATIONS = (
    ColumnMigration("event", "organization_id", "ALTER TABLE event ADD COLUMN organization_id INTEGER REFERENCES organization(id)"),
    ColumnMigration("event_stage", "organization_name", "ALTER TABLE event_stage ADD COLUMN organization_name VARCHAR(255)"),
    ColumnMigration("catalog", "related_ids", "ALTER TABLE catalog ADD COLUMN related_ids JSON"),
    ColumnMigration("place", "legistar_client", "ALTER TABLE place ADD COLUMN legistar_client VARCHAR(100)"),
    ColumnMigration("person", "is_elected", "ALTER TABLE person ADD COLUMN is_elected BOOLEAN DEFAULT FALSE", "CREATE INDEX IF NOT EXISTS ix_person_is_elected ON person (is_elected)"),
    ColumnMigration("person", "person_type", "ALTER TABLE person ADD COLUMN person_type VARCHAR(20) NOT NULL DEFAULT 'mentioned'", "CREATE INDEX IF NOT EXISTS ix_person_person_type ON person (person_type)"),
    ColumnMigration("catalog", "content_hash", "ALTER TABLE catalog ADD COLUMN content_hash VARCHAR(64)"),
    ColumnMigration("catalog", "summary_source_hash", "ALTER TABLE catalog ADD COLUMN summary_source_hash VARCHAR(64)"),
    ColumnMigration("catalog", "topics_source_hash", "ALTER TABLE catalog ADD COLUMN topics_source_hash VARCHAR(64)"),
    ColumnMigration("agenda_item", "page_number", "ALTER TABLE agenda_item ADD COLUMN page_number INTEGER"),
    ColumnMigration("agenda_item", "text_offset", "ALTER TABLE agenda_item ADD COLUMN text_offset INTEGER"),
    ColumnMigration("agenda_item", "votes", "ALTER TABLE agenda_item ADD COLUMN votes JSON"),
    ColumnMigration("agenda_item", "raw_history", "ALTER TABLE agenda_item ADD COLUMN raw_history TEXT"),
    ColumnMigration("agenda_item", "legistar_matter_id", "ALTER TABLE agenda_item ADD COLUMN legistar_matter_id INTEGER", "CREATE INDEX IF NOT EXISTS ix_agenda_item_legistar_matter_id ON agenda_item (legistar_matter_id)"),
    ColumnMigration("agenda_item", "spatial_coords", "ALTER TABLE agenda_item ADD COLUMN spatial_coords JSON"),
    ColumnMigration("catalog", "agenda_segmentation_status", "ALTER TABLE catalog ADD COLUMN agenda_segmentation_status VARCHAR(20)", "CREATE INDEX IF NOT EXISTS ix_catalog_agenda_segmentation_status ON catalog (agenda_segmentation_status)"),
    ColumnMigration("catalog", "agenda_segmentation_attempted_at", "ALTER TABLE catalog ADD COLUMN agenda_segmentation_attempted_at TIMESTAMP", "CREATE INDEX IF NOT EXISTS ix_catalog_agenda_segmentation_attempted_at ON catalog (agenda_segmentation_attempted_at)"),
    ColumnMigration("catalog", "agenda_segmentation_item_count", "ALTER TABLE catalog ADD COLUMN agenda_segmentation_item_count INTEGER"),
    ColumnMigration("catalog", "agenda_segmentation_error", "ALTER TABLE catalog ADD COLUMN agenda_segmentation_error TEXT"),
    ColumnMigration("catalog", "extraction_status", "ALTER TABLE catalog ADD COLUMN extraction_status VARCHAR(20)", "CREATE INDEX IF NOT EXISTS ix_catalog_extraction_status ON catalog (extraction_status)"),
    ColumnMigration("catalog", "extraction_attempted_at", "ALTER TABLE catalog ADD COLUMN extraction_attempted_at TIMESTAMP", "CREATE INDEX IF NOT EXISTS ix_catalog_extraction_attempted_at ON catalog (extraction_attempted_at)"),
    ColumnMigration("catalog", "extraction_attempt_count", "ALTER TABLE catalog ADD COLUMN extraction_attempt_count INTEGER"),
    ColumnMigration("catalog", "extraction_error", "ALTER TABLE catalog ADD COLUMN extraction_error TEXT"),
    ColumnMigration("catalog", "entities_source_hash", "ALTER TABLE catalog ADD COLUMN entities_source_hash VARCHAR(64)"),
    ColumnMigration("catalog", "agenda_items_hash", "ALTER TABLE catalog ADD COLUMN agenda_items_hash VARCHAR(64)"),
)


def postgres_column_exists(conn: Connection, table: str, column: str) -> bool:
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


def add_column_if_missing(conn: Connection, table: str, column: str, ddl: str, logger: logging.Logger) -> bool:
    if postgres_column_exists(conn, table, column):
        logger.info("migration_skip table=%s column=%s reason=already_present", table, column)
        return False
    conn.execute(text(ddl))
    logger.info("migration_apply table=%s column=%s", table, column)
    return True


def apply_core_column_migrations(conn: Connection, logger: logging.Logger) -> None:
    for column_migration in CORE_COLUMN_MIGRATIONS:
        added = add_column_if_missing(
            conn,
            column_migration.table,
            column_migration.column,
            column_migration.ddl,
            logger,
        )
        if added and column_migration.index_sql:
            conn.execute(text(column_migration.index_sql))

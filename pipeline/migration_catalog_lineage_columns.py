from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Connection

from pipeline.db_migration_columns import ColumnMigration, postgres_column_exists


POSTGRESQL_DIALECT = "postgresql"
LINEAGE_COLUMN_MIGRATIONS = (
    ColumnMigration(
        "catalog",
        "lineage_id",
        "ALTER TABLE catalog ADD COLUMN lineage_id VARCHAR(64)",
        "CREATE INDEX IF NOT EXISTS ix_catalog_lineage_id ON catalog (lineage_id)",
    ),
    ColumnMigration(
        "catalog",
        "lineage_confidence",
        "ALTER TABLE catalog ADD COLUMN lineage_confidence DOUBLE PRECISION",
        "CREATE INDEX IF NOT EXISTS ix_catalog_lineage_confidence ON catalog (lineage_confidence)",
    ),
    ColumnMigration(
        "catalog",
        "lineage_updated_at",
        "ALTER TABLE catalog ADD COLUMN lineage_updated_at TIMESTAMP",
        "CREATE INDEX IF NOT EXISTS ix_catalog_lineage_updated_at ON catalog (lineage_updated_at)",
    ),
)


def migrate(connection: Connection) -> None:
    if connection.dialect.name != POSTGRESQL_DIALECT:
        return

    for column_migration in LINEAGE_COLUMN_MIGRATIONS:
        if not postgres_column_exists(
            connection,
            column_migration.table,
            column_migration.column,
        ):
            connection.execute(text(column_migration.ddl))
        if column_migration.index_sql:
            connection.execute(text(column_migration.index_sql))

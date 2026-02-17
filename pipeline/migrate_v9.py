from __future__ import annotations

import logging
from sqlalchemy import text

from pipeline.models import db_connect

logger = logging.getLogger("migrate-v9")


def _column_exists(conn, table: str, column: str) -> bool:
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
    if engine.dialect.name != "postgresql":
        return

    with engine.begin() as conn:
        if not _column_exists(conn, "catalog", "lineage_id"):
            conn.execute(text("ALTER TABLE catalog ADD COLUMN lineage_id VARCHAR(64)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_catalog_lineage_id ON catalog (lineage_id)"))

        if not _column_exists(conn, "catalog", "lineage_confidence"):
            conn.execute(text("ALTER TABLE catalog ADD COLUMN lineage_confidence DOUBLE PRECISION"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_catalog_lineage_confidence ON catalog (lineage_confidence)"))

        if not _column_exists(conn, "catalog", "lineage_updated_at"):
            conn.execute(text("ALTER TABLE catalog ADD COLUMN lineage_updated_at TIMESTAMP"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_catalog_lineage_updated_at ON catalog (lineage_updated_at)"))


if __name__ == "__main__":
    migrate()

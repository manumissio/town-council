from __future__ import annotations

from collections.abc import Callable

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from pipeline.models import db_connect


DbConnectCallable = Callable[[], Engine]
ColumnExistsCallable = Callable[[Connection, str, str], bool]


def column_exists(conn: Connection, table: str, column: str) -> bool:
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


def migrate(
    *,
    db_connect_callable: DbConnectCallable = db_connect,
    column_exists_callable: ColumnExistsCallable = column_exists,
) -> None:
    engine = db_connect_callable()
    if engine.dialect.name != "postgresql":
        return

    with engine.begin() as conn:
        _add_lineage_column(conn, "lineage_id", "VARCHAR(64)", "ix_catalog_lineage_id", column_exists_callable)
        _add_lineage_column(
            conn,
            "lineage_confidence",
            "DOUBLE PRECISION",
            "ix_catalog_lineage_confidence",
            column_exists_callable,
        )
        _add_lineage_column(
            conn, "lineage_updated_at", "TIMESTAMP", "ix_catalog_lineage_updated_at", column_exists_callable
        )


def _add_lineage_column(
    conn: Connection,
    column: str,
    column_type: str,
    index_name: str,
    column_exists_callable: ColumnExistsCallable,
) -> None:
    if column_exists_callable(conn, "catalog", column):
        return
    conn.execute(text(f"ALTER TABLE catalog ADD COLUMN {column} {column_type}"))
    conn.execute(text(f"CREATE INDEX IF NOT EXISTS {index_name} ON catalog ({column})"))

from __future__ import annotations

from sqlalchemy.engine import Connection

from pipeline.migration_catalog_lineage_columns import migrate as migrate_connection
from pipeline.models import db_connect


def migrate(connection: Connection | None = None) -> None:
    if connection is not None:
        migrate_connection(connection)
        return

    engine = db_connect()
    with engine.begin() as owned_connection:
        migrate_connection(owned_connection)


if __name__ == "__main__":
    migrate()

from __future__ import annotations

from sqlalchemy.engine import Connection

from pipeline.migration_pgvector_semantic_embeddings import migrate as migrate_connection
from pipeline.models import db_connect


def migrate(connection: Connection | None = None) -> int:
    if connection is not None:
        return migrate_connection(connection)

    engine = db_connect()
    with engine.begin() as owned_connection:
        return migrate_connection(owned_connection)


if __name__ == "__main__":
    migrate()

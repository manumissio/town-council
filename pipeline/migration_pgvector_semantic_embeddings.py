from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Connection

from pipeline.db_migration_columns import postgres_column_exists


POSTGRESQL_DIALECT = "postgresql"
RETIRED_CATALOG_VECTOR_COLUMN = "semantic_embedding"
RETIRED_CATALOG_VECTOR_COUNT_SQL = (
    "SELECT count(*) FROM catalog WHERE semantic_embedding IS NOT NULL"
)
FROZEN_V8_STATEMENTS = (
    "CREATE EXTENSION IF NOT EXISTS vector",
    """
    CREATE TABLE IF NOT EXISTS semantic_embedding (
        id SERIAL PRIMARY KEY,
        catalog_id INTEGER REFERENCES catalog(id) ON DELETE CASCADE,
        agenda_item_id INTEGER REFERENCES agenda_item(id) ON DELETE CASCADE,
        model_name VARCHAR(120) NOT NULL,
        embedding_dim INTEGER NOT NULL,
        embedding VECTOR(384),
        source_hash VARCHAR(64),
        updated_at TIMESTAMP DEFAULT now(),
        CONSTRAINT check_single_entity_reference CHECK (
            (catalog_id IS NOT NULL AND agenda_item_id IS NULL)
            OR (catalog_id IS NULL AND agenda_item_id IS NOT NULL)
        )
    )
    """,
    "ALTER TABLE catalog DROP COLUMN IF EXISTS semantic_embedding",
    """
    CREATE UNIQUE INDEX IF NOT EXISTS ix_semantic_embedding_catalog_model
    ON semantic_embedding (catalog_id, model_name)
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS ix_semantic_embedding_item_model
    ON semantic_embedding (agenda_item_id, model_name)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_semantic_embedding_hnsw
    ON semantic_embedding
    USING hnsw (embedding vector_cosine_ops)
    WHERE embedding IS NOT NULL
    """,
)


def migrate(connection: Connection) -> int:
    if connection.dialect.name != POSTGRESQL_DIALECT:
        return 0

    retired_catalog_vector_count = _retired_catalog_vector_count(connection)
    for migration_statement in FROZEN_V8_STATEMENTS:
        connection.execute(text(migration_statement))
    return retired_catalog_vector_count


def _retired_catalog_vector_count(connection: Connection) -> int:
    if not postgres_column_exists(
        connection,
        "catalog",
        RETIRED_CATALOG_VECTOR_COLUMN,
    ):
        return 0
    retired_catalog_vector_count = connection.execute(
        text(RETIRED_CATALOG_VECTOR_COUNT_SQL)
    ).scalar_one()
    if not isinstance(retired_catalog_vector_count, int):
        raise RuntimeError("Invalid retired catalog vector count")
    return retired_catalog_vector_count

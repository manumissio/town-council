from __future__ import annotations

from collections.abc import Callable

from sqlalchemy import MetaData, text
from sqlalchemy.engine import Engine

from pipeline.models import Base, db_connect


DbConnectCallable = Callable[[], Engine]


def migrate(
    *,
    db_connect_callable: DbConnectCallable = db_connect,
    model_metadata: MetaData = Base.metadata,
) -> None:
    """
    Milestone B2 migration: enable pgvector and create dedicated semantic_embedding table.

    Order matters:
    1) extension
    2) table creation
    3) cleanup + ANN index
    """
    engine = db_connect_callable()
    if engine.dialect.name != "postgresql":
        return

    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

    model_metadata.create_all(engine)

    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE catalog DROP COLUMN IF EXISTS semantic_embedding"))
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_semantic_embedding_hnsw
                ON semantic_embedding
                USING hnsw (embedding vector_cosine_ops)
                WHERE embedding IS NOT NULL
                """
            )
        )

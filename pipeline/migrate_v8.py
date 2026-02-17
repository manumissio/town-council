from __future__ import annotations

import logging
from sqlalchemy import text

from pipeline.models import Base, db_connect

logger = logging.getLogger("migrate-v8")


def migrate() -> None:
    """
    Milestone B2 migration: enable pgvector and create dedicated semantic_embedding table.

    Order matters:
    1) extension
    2) table creation
    3) cleanup + ANN index
    """
    engine = db_connect()
    if engine.dialect.name != "postgresql":
        return

    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

    # Ensure model-backed tables exist after extension is available.
    Base.metadata.create_all(engine)

    with engine.begin() as conn:
        # Retire the early B2 scaffold column once dedicated table exists.
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


if __name__ == "__main__":
    migrate()

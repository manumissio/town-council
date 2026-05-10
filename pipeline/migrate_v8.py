from __future__ import annotations

from pipeline.migration_pgvector_semantic_embeddings import Base as Base, db_connect as db_connect
from pipeline.migration_pgvector_semantic_embeddings import migrate as migrate_impl


def migrate() -> None:
    migrate_impl(db_connect_callable=db_connect, model_metadata=Base.metadata)


if __name__ == "__main__":
    migrate()

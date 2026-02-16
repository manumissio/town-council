"""
Rebuild semantic search artifacts from Postgres (no extraction, no Meilisearch indexing).
"""

from pipeline.db_session import db_session
from pipeline.semantic_index import get_semantic_backend


def main() -> int:
    backend = get_semantic_backend()
    with db_session() as db:
        result = backend.build_index(db)
    print("semantic_reindex_complete")
    print(f"model={result.model_name}")
    print(f"built_at={result.built_at}")
    print(f"rows={result.row_count}")
    print(f"catalogs={result.catalog_count}")
    print(f"source_counts={result.source_counts}")
    print(f"corpus_hash={result.corpus_hash}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

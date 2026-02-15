"""
Reindex Meilisearch from the current Postgres state (no extraction, no AI).

Why this exists:
Sometimes you change how we index documents (or you fix bad HTML stored in agenda item titles)
and you need Meilisearch to be refreshed without re-running the full pipeline.

Usage (Docker):
  docker compose run --rm pipeline python reindex_only.py
  docker compose run --rm pipeline python reindex_only.py --catalog-id 609
"""

import argparse

from pipeline.indexer import index_documents, reindex_catalog


def main() -> int:
    parser = argparse.ArgumentParser(description="Reindex Meilisearch from Postgres only.")
    parser.add_argument(
        "--catalog-id",
        type=int,
        default=None,
        help="If provided, reindex only this one catalog. Otherwise, reindex all documents and agenda items.",
    )
    args = parser.parse_args()

    if args.catalog_id is not None:
        reindex_catalog(args.catalog_id)
        return 0

    index_documents()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


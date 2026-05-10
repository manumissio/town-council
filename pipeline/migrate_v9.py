from __future__ import annotations

from pipeline.migration_catalog_lineage_columns import column_exists, db_connect as db_connect, migrate as migrate_impl

_column_exists = column_exists


def migrate() -> None:
    migrate_impl(db_connect_callable=db_connect, column_exists_callable=_column_exists)


if __name__ == "__main__":
    migrate()

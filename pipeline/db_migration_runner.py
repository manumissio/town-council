from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy.engine import Connection

from pipeline.db_migration_backfills import run_core_backfills
from pipeline.db_migration_columns import (
    apply_core_column_migrations,
    apply_core_constraint_repairs,
)
from pipeline.migrate_v10 import migrate as migrate_v10
from pipeline.migrate_v8 import migrate as migrate_v8
from pipeline.migrate_v9 import migrate as migrate_v9


@dataclass(frozen=True, slots=True)
class LegacyMigrationReport:
    retired_catalog_vector_count: int


def run_migrations(
    connection: Connection,
    logger: logging.Logger,
) -> LegacyMigrationReport:
    if connection.dialect.name != "postgresql":
        return LegacyMigrationReport(retired_catalog_vector_count=0)
    apply_core_column_migrations(connection, logger)
    run_core_backfills(connection)
    apply_core_constraint_repairs(connection)
    retired_catalog_vector_count = migrate_v8(connection)
    migrate_v9(connection)
    migrate_v10(connection)
    return LegacyMigrationReport(
        retired_catalog_vector_count=retired_catalog_vector_count,
    )

from __future__ import annotations

import logging
from collections.abc import Callable
from types import ModuleType

from sqlalchemy.engine import Engine

from pipeline.db_migration_backfills import run_core_backfills
from pipeline.db_migration_columns import apply_core_column_migrations


DbConnectCallable = Callable[[], Engine]


def run_migrations(
    *,
    db_connect_callable: DbConnectCallable,
    migrate_v8_module: ModuleType,
    migrate_v9_module: ModuleType,
    logger: logging.Logger,
) -> None:
    engine = db_connect_callable()
    with engine.begin() as conn:
        if engine.dialect.name != "postgresql":
            return
        apply_core_column_migrations(conn, logger)
        run_core_backfills(conn)

    _run_submigration(migrate_v8_module, "migrate_v8", logger)
    _run_submigration(migrate_v9_module, "migrate_v9", logger)


def _run_submigration(migration_module: ModuleType, migration_label: str, logger: logging.Logger) -> None:
    try:
        migration_module.migrate()
    except Exception as exc:
        logger.warning("%s skipped: %s", migration_label, exc)

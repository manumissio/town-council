from __future__ import annotations

import logging

from pipeline import db_migration_alembic
from pipeline.cli_logging import configure_cli_logging
from pipeline.models import db_connect


LOGGER = logging.getLogger("db-migrate")
LOGGER_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"


def migrate() -> None:
    engine = db_connect()
    try:
        migration_outcome = db_migration_alembic.migrate_database(engine)
        LOGGER.info(
            "database_migration_complete status=%s revision=%s "
            "retired_catalog_vector_count=%d",
            migration_outcome.status,
            migration_outcome.revision,
            migration_outcome.retired_vector_count,
        )
    finally:
        engine.dispose()


def main() -> int:
    configure_cli_logging(LOGGER_FORMAT)
    migrate()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

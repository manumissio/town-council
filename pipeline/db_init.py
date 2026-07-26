import logging

from pipeline import db_migrate
from pipeline.cli_logging import configure_cli_logging

LOGGER_NAME = "db-init"
LOGGER_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"

logger = logging.getLogger(LOGGER_NAME)


def _configure_cli_logging() -> None:
    """Keep logging setup at the entrypoint so imports stay side-effect free."""
    configure_cli_logging(LOGGER_FORMAT)


def init_db() -> None:
    """Apply the canonical migration path for fresh and existing databases."""
    logger.info("Applying database migrations...")
    db_migrate.migrate()
    logger.info("Database migration complete.")


def main() -> int:
    _configure_cli_logging()
    init_db()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

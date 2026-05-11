import logging

from pipeline.cli_logging import configure_cli_logging
from pipeline.models import db_connect, create_tables

LOGGER_NAME = "db-init"
LOGGER_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"

logger = logging.getLogger(LOGGER_NAME)


def _configure_cli_logging() -> None:
    """Keep logging setup at the entrypoint so imports stay side-effect free."""
    configure_cli_logging(LOGGER_FORMAT)


def init_db():
    """
    Explicitly creates the database tables.
    Run this script once when setting up the system.
    """
    logger.info("Connecting to database...")
    engine = db_connect()
    
    logger.info("Creating tables...")
    create_tables(engine)
    
    logger.info("Database initialization complete.")


def main() -> int:
    _configure_cli_logging()
    init_db()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

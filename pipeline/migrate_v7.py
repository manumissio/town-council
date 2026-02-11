from sqlalchemy import text
import logging

from pipeline.models import db_connect

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("migration_v7")


def migrate():
    """
    Migration v7: add hash fields to track staleness for derived content.

    Adds:
    - catalog.content_hash
    - catalog.summary_source_hash
    - catalog.topics_source_hash

    Note:
    Backfill is intentionally done in a separate script so we don't depend on
    database-specific crypto extensions (and so it's easy to re-run safely).
    """
    engine = db_connect()

    with engine.connect() as conn:
        for col in ("content_hash", "summary_source_hash", "topics_source_hash"):
            try:
                logger.info(f"Adding {col} column to catalog table...")
                conn.execute(text(f"ALTER TABLE catalog ADD COLUMN {col} VARCHAR(64)"))
                conn.commit()
                logger.info(f"✓ Added catalog.{col}")
            except Exception as e:
                msg = str(e).lower()
                if "duplicate column" in msg or "already exists" in msg:
                    logger.info(f"✓ catalog.{col} already exists")
                else:
                    logger.warning(f"Could not add catalog.{col}: {e}")

        logger.info("Migration v7 complete!")


if __name__ == "__main__":
    migrate()


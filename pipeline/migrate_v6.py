from pipeline.models import db_connect
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("migration_v6")


def migrate():
    """
    Migration v6: classify Person rows as official vs mention-only.

    Changes:
    - Add person.person_type with default 'mentioned'
    - Add index on person_type
    - Backfill a safe first-pass:
      * 'official' for rows with elected flag, official-style role, or memberships
      * 'mentioned' for everything else
    """
    engine = db_connect()

    with engine.connect() as conn:
        try:
            logger.info("Adding person_type column to person table...")
            conn.execute(text("ALTER TABLE person ADD COLUMN person_type VARCHAR(20) DEFAULT 'mentioned'"))
            conn.commit()
            logger.info("✓ Added person_type to person")
        except Exception as e:
            if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
                logger.info("✓ person_type column already exists in person")
            else:
                logger.warning(f"Could not add person_type to person: {e}")

        try:
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_person_person_type ON person(person_type)"))
            conn.commit()
            logger.info("✓ Added ix_person_person_type index")
        except Exception as e:
            logger.warning(f"Could not add ix_person_person_type: {e}")

        try:
            # Start from a conservative default.
            conn.execute(text("UPDATE person SET person_type = 'mentioned' WHERE person_type IS NULL OR person_type = ''"))
            # Promote rows with strong existing evidence.
            conn.execute(text(
                """
                UPDATE person
                SET person_type = 'official'
                WHERE is_elected = 1
                   OR lower(coalesce(current_role, '')) LIKE '%mayor%'
                   OR lower(coalesce(current_role, '')) LIKE '%council%'
                   OR lower(coalesce(current_role, '')) LIKE '%commissioner%'
                   OR id IN (SELECT person_id FROM membership)
                """
            ))
            conn.commit()
            logger.info("✓ Backfilled person_type")
        except Exception as e:
            logger.warning(f"Could not backfill person_type: {e}")

        logger.info("Migration v6 complete!")


if __name__ == "__main__":
    migrate()

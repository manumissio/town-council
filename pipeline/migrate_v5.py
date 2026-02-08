from pipeline.models import db_connect
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("migration_v5")

def migrate():
    """
    Migration v5: Add schema changes for ground truth verification and improved data model.

    Schema changes:
    - Place: Add legistar_client column for API key storage
    - Person: Add is_elected boolean flag for filtering elected officials
    - AgendaItem: Expand description to TEXT, add page_number, text_offset for deep linking
    - AgendaItem: Add votes, raw_history, legistar_matter_id, spatial_coords for verification
    """
    engine = db_connect()

    with engine.connect() as conn:
        # Note: SQLite doesn't have information_schema, so we use a different approach
        # We'll try to add each column and catch the error if it already exists

        # 1. Add legistar_client to Place table
        try:
            logger.info("Adding legistar_client column to place table...")
            conn.execute(text("ALTER TABLE place ADD COLUMN legistar_client VARCHAR(100)"))
            conn.commit()
            logger.info("✓ Added legistar_client to place")
        except Exception as e:
            if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
                logger.info("✓ legistar_client column already exists in place")
            else:
                logger.warning(f"Could not add legistar_client to place: {e}")

        # 2. Add is_elected to Person table
        try:
            logger.info("Adding is_elected column to person table...")
            conn.execute(text("ALTER TABLE person ADD COLUMN is_elected BOOLEAN DEFAULT 0"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_person_is_elected ON person(is_elected)"))
            conn.commit()
            logger.info("✓ Added is_elected to person")
        except Exception as e:
            if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
                logger.info("✓ is_elected column already exists in person")
            else:
                logger.warning(f"Could not add is_elected to person: {e}")

        # 3. Add new columns to AgendaItem table
        agenda_item_columns = [
            ("page_number", "INTEGER"),
            ("text_offset", "INTEGER"),
            ("votes", "JSON"),
            ("raw_history", "TEXT"),
            ("legistar_matter_id", "INTEGER"),
            ("spatial_coords", "JSON")
        ]

        for col_name, col_type in agenda_item_columns:
            try:
                logger.info(f"Adding {col_name} column to agenda_item table...")
                conn.execute(text(f"ALTER TABLE agenda_item ADD COLUMN {col_name} {col_type}"))

                # Add index for legistar_matter_id
                if col_name == "legistar_matter_id":
                    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_agenda_item_legistar_matter_id ON agenda_item(legistar_matter_id)"))

                conn.commit()
                logger.info(f"✓ Added {col_name} to agenda_item")
            except Exception as e:
                if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
                    logger.info(f"✓ {col_name} column already exists in agenda_item")
                else:
                    logger.warning(f"Could not add {col_name} to agenda_item: {e}")

        logger.info("Migration v5 complete!")

if __name__ == "__main__":
    migrate()

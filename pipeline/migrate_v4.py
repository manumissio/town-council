from pipeline.models import db_connect
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("migration")

def migrate():
    engine = db_connect()
    with engine.connect() as conn:
        logger.info("Checking for related_ids column...")
        res = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='catalog' AND column_name='related_ids'"))
        if res.fetchone() is None:
            logger.info("Adding related_ids column to catalog table...")
            conn.execute(text("ALTER TABLE catalog ADD COLUMN related_ids JSON"))
            conn.commit()
            logger.info("Migration successful.")
        else:
            logger.info("Column related_ids already exists.")

if __name__ == "__main__":
    migrate()

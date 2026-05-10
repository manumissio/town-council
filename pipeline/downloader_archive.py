import logging

from sqlalchemy import bindparam, text

logger = logging.getLogger(__name__)


def archive_url_stage(processed_ids, *, db_connect_func):
    """Move successfully processed staged rows to history."""
    if not processed_ids:
        return

    engine = db_connect_func()
    with engine.begin() as conn:
        logger.info(f"Archiving {len(processed_ids)} processed URLs to history...")
        insert_stmt = text(
            "INSERT INTO url_stage_hist (ocd_division_id, event, event_date, url, url_hash, category, created_at) "
            "SELECT ocd_division_id, event, event_date, url, url_hash, category, created_at "
            "FROM url_stage WHERE id IN :ids"
        ).bindparams(bindparam("ids", expanding=True))
        delete_stmt = text("DELETE FROM url_stage WHERE id IN :ids").bindparams(bindparam("ids", expanding=True))
        conn.execute(insert_stmt, {"ids": processed_ids})
        conn.execute(delete_stmt, {"ids": processed_ids})
        logger.info("Processed staging rows archived.")

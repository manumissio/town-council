import logging
from concurrent.futures import ThreadPoolExecutor

from pipeline.config import DOWNLOAD_WORKERS
from pipeline.db_session import db_session
from pipeline.downloader_archive import archive_url_stage as _archive_url_stage
from pipeline.downloader_media import Media
from pipeline.downloader_processing import process_single_url as _process_single_url
from pipeline.downloader_selection import _select_staged_url_ids
from pipeline.models import db_connect

logger = logging.getLogger(__name__)

__all__ = [
    "Media",
    "ThreadPoolExecutor",
    "archive_url_stage",
    "db_connect",
    "db_session",
    "_select_staged_url_ids",
    "process_single_url",
    "process_staged_urls",
]


def process_single_url(url_record_id):
    """
    Process one staged URL and link it to catalog/document rows.
    """
    return _process_single_url(
        url_record_id,
        db_session_factory=db_session,
        media_cls=Media,
    )


def process_staged_urls():
    """
    Download staged URLs in parallel and persist document links.
    """
    with db_session() as session:
        url_ids = _select_staged_url_ids(session)

    if not url_ids:
        logger.info("No URLs in staging table to process.")
        return

    logger.info(f"Processing {len(url_ids)} staged URLs using {DOWNLOAD_WORKERS} threads...")

    # Network-bound downloads benefit from thread-level concurrency.
    with ThreadPoolExecutor(max_workers=DOWNLOAD_WORKERS) as executor:
        results = list(executor.map(process_single_url, url_ids))

    # Archive only rows that were processed successfully.
    processed_ids = [url_id for url_id, ok in zip(url_ids, results) if ok]
    if processed_ids:
        archive_url_stage(processed_ids)
    else:
        logger.warning("No staged URLs were successfully processed; keeping staging rows for retry.")


def archive_url_stage(processed_ids):
    """Move successfully processed staged rows to history."""
    return _archive_url_stage(processed_ids, db_connect_func=db_connect)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    process_staged_urls()

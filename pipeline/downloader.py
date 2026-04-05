import os
import requests
import logging
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy import text, bindparam
from sqlalchemy.exc import SQLAlchemyError

from pipeline.models import Place, UrlStage, Event, Catalog, Document, db_connect
from pipeline.db_session import db_session
from pipeline.config import (
    MAX_FILE_SIZE_BYTES,
    FILE_WRITE_CHUNK_SIZE,
    DOWNLOAD_TIMEOUT_SECONDS,
    DOWNLOAD_WORKERS
)

logger = logging.getLogger(__name__)
ISO_FMT = "%Y-%m-%dT%H:%M:%SZ"
DEFAULT_CONTENT_TYPE = 'application/pdf'
PDF_CONTENT_MARKER = 'pdf'
HTML_CONTENT_MARKER = 'html'
DEFAULT_DOCUMENT_EXTENSION = '.pdf'
FALLBACK_OCD_DIRECTORY = "misc"


def _parse_onboarding_started_at(raw_value: str | None):
    value = str(raw_value or "").strip()
    if not value:
        return None
    try:
        return datetime.strptime(value, ISO_FMT).replace(tzinfo=timezone.utc).replace(tzinfo=None)
    except ValueError:
        logger.warning("downloader_onboarding_scope invalid_started_at=%r", value)
        return None


def _select_staged_url_ids(session) -> list[int]:
    query = session.query(UrlStage.id)
    onboarding_city = str(os.getenv("PIPELINE_ONBOARDING_CITY", "") or "").strip()
    if not onboarding_city:
        return [r.id for r in query.all()]

    # Onboarding validation should only pull staged URLs created by the current
    # city run, otherwise unrelated backlog can leak into the city verdict.
    onboarding_ocd_division_id = f"ocd-division/country:us/state:ca/place:{onboarding_city}"
    query = query.filter(UrlStage.ocd_division_id == onboarding_ocd_division_id)

    onboarding_started_at = _parse_onboarding_started_at(os.getenv("PIPELINE_ONBOARDING_STARTED_AT_UTC"))
    if onboarding_started_at is not None:
        query = query.filter(UrlStage.created_at >= onboarding_started_at)

    return [r.id for r in query.all()]

class Media():
    """
    Handles the downloading of documents (PDFs, HTML) from the web.
    """
    def __init__(self, doc):
        # Use DATA_DIR from environment or default to local data folder
        self.working_dir = os.getenv('DATA_DIR', './data')
        self.doc = doc
        # Security: Disable trust_env. This prevents the request from accidentally
        # using credentials stored in a local .netrc file, which is a security risk (CVE-2024-3651).
        self.session = requests.Session()
        self.session.trust_env = False

    def gather(self):
        """
        Download and store one document. Return local path or None.
        """
        # Fetch the document from the URL
        self.response = self._get_document(self.doc.url)
        
        # Check if we got a valid response (not an error code or None)
        if self.response and not isinstance(self.response, int):
            content_type = self._parse_content_type(self.response.headers)
            file_location = self._store_document(
                    self.response, content_type, self.doc.url_hash)
            return file_location
        else:
            return None

    def _parse_content_type(self, headers):
        """
        Normalize response content type for extension detection.
        """
        content_type = headers.get('Content-Type', DEFAULT_CONTENT_TYPE)
        content_type = content_type.split(';')[0]  # Remove charset if present (e.g., "text/html; charset=utf-8")
        return content_type

    def _get_document(self, document_url):
        """
        Download a document with streaming and timeout protection.
        """
        try:
            # Stream response so large files do not load fully into memory.
            r = self.session.get(document_url, stream=True, timeout=DOWNLOAD_TIMEOUT_SECONDS)

            if r.ok:
                # Reject files above configured maximum size.
                content_length = r.headers.get('Content-Length')
                if content_length and int(content_length) > MAX_FILE_SIZE_BYTES:
                    logger.warning(
                        "download_skip_oversized url=%s content_length=%s max_bytes=%s",
                        document_url,
                        content_length,
                        MAX_FILE_SIZE_BYTES,
                    )
                    return None
                return r
            else:
                return r.status_code
        except requests.RequestException as e:
            # Any network failure returns None so caller can skip safely.
            logger.error("download_request_failed url=%s error=%s", document_url, e)
            return None

    def _store_document(self, response, content_type, url_hash):
        """
        Save downloaded bytes to local disk.
        """
        file_path = self._create_fp_from_ocd_id(self.doc.ocd_division_id)
        
        # Determine the correct file extension
        if PDF_CONTENT_MARKER in content_type:
            ext = DEFAULT_DOCUMENT_EXTENSION
        elif HTML_CONTENT_MARKER in content_type:
            ext = '.html'
        else:
            # Default to .pdf if unknown as most meeting docs are PDFs
            ext = DEFAULT_DOCUMENT_EXTENSION

        full_path = os.path.join(file_path, f'{url_hash}{ext}')
        # Ensure we store the absolute path in the database
        abs_path = os.path.abspath(full_path)

        # Write in chunks to keep memory usage low.
        try:
            with open(abs_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=FILE_WRITE_CHUNK_SIZE):
                    f.write(chunk)
            return abs_path
        except OSError as e:
            logger.error(f"Failed to write file {abs_path}: {e}")
            return None

    def _create_fp_from_ocd_id(self, ocd_id_str):
        """
        Build a city-specific data directory from OCD division ID.
        """
        try:
            if not ocd_id_str or '/' not in ocd_id_str:
                raise ValueError("Missing '/' separator")
                
            parts = ocd_id_str.split('/')
            location_segments = parts[1:]
            
            segments = []
            for token in location_segments:
                if ':' in token:
                    segments.append(token.split(':')[1])
            
            if not segments:
                raise ValueError("No valid location segments found")
                
            safe_path = os.path.join(self.working_dir, *segments)
            os.makedirs(safe_path, exist_ok=True)
            return safe_path

        except (ValueError, OSError) as e:
            # Keep ingestion moving even when location metadata is malformed.
            logger.warning(
                "downloader_ocd_fallback ocd_division_id=%r error=%s fallback_dir=%s",
                ocd_id_str,
                e,
                FALLBACK_OCD_DIRECTORY,
            )
            fallback_path = os.path.join(self.working_dir, FALLBACK_OCD_DIRECTORY)
            os.makedirs(fallback_path, exist_ok=True)
            return fallback_path


def process_single_url(url_record_id):
    """
    Process one staged URL and link it to catalog/document rows.
    """
    try:
        with db_session() as session:
            url_record = session.get(UrlStage, url_record_id)
            if not url_record:
                return False

            # Find the matching event so the downloaded file can be linked.
            event_record = session.query(Event).filter(
                Event.ocd_division_id == url_record.ocd_division_id,
                Event.record_date == url_record.event_date,
                Event.name == url_record.event
            ).first()
        
            if not event_record:
                logger.info(
                    "downloader_skip_missing_event url_record_id=%s event=%s event_date=%s",
                    url_record_id,
                    url_record.event,
                    url_record.event_date,
                )
                return False

            # Reuse existing catalog row when URL hash already exists.
            catalog_entry = session.query(Catalog).filter(
                Catalog.url_hash == url_record.url_hash
            ).first()

            if not catalog_entry:
                logger.info("downloader_fetch_start url_record_id=%s url=%s", url_record_id, url_record.url)
                downloader = Media(url_record)
                file_location = downloader.gather()

                if file_location:
                    try:
                        catalog_entry = Catalog(
                            url=url_record.url,
                            url_hash=url_record.url_hash,
                            location=file_location,
                            filename=os.path.basename(file_location)
                        )
                        session.add(catalog_entry)
                        session.flush()
                    except SQLAlchemyError:
                        # Another worker may have inserted the same hash first.
                        session.rollback()
                        logger.info(
                            "downloader_catalog_race_recovered url_record_id=%s url_hash=%s",
                            url_record_id,
                            url_record.url_hash,
                        )
                        catalog_entry = session.query(Catalog).filter(
                            Catalog.url_hash == url_record.url_hash
                        ).first()
                else:
                    logger.error("downloader_fetch_failed url_record_id=%s url=%s", url_record_id, url_record.url)
                    return False

            # Avoid duplicate event/catalog links.
            existing_doc = session.query(Document).filter(
                Document.event_id == event_record.id,
                Document.catalog_id == catalog_entry.id
            ).first()

            if not existing_doc:
                document = Document(
                    place_id=event_record.place_id,
                    event_id=event_record.id,
                    catalog_id=catalog_entry.id,
                    url=url_record.url,
                    url_hash=url_record.url_hash,
                    category=url_record.category
                )
                session.add(document)
        
            session.commit()
            return True
    except SQLAlchemyError as e:
        logger.error("downloader_process_failed url_record_id=%s error=%s", url_record_id, e)
        return False
        


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
    if not processed_ids:
        return

    engine = db_connect()
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


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    process_staged_urls()

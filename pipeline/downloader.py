import os
import requests
import logging
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from pipeline.models import Place, UrlStage, Event, Catalog, Document, UrlStageHist
from pipeline.db_session import db_session
from pipeline.config import (
    MAX_FILE_SIZE_BYTES,
    FILE_WRITE_CHUNK_SIZE,
    DOWNLOAD_TIMEOUT_SECONDS,
    DOWNLOAD_WORKERS
)

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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
        Main method to fetch and save the document.
        Returns the local file path if successful, or None if failed.
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
        Reads the 'Content-Type' header to determine if the file is a PDF or HTML.
        Defaults to PDF if not specified.
        """
        content_type = headers.get('Content-Type', 'application/pdf')
        content_type = content_type.split(';')[0]  # Remove charset if present (e.g., "text/html; charset=utf-8")
        return content_type

    def _get_document(self, document_url):
        """
        Downloads the file from the given URL.

        What this does:
        1. Checks file size BEFORE downloading (prevents memory issues)
        2. Uses streaming to avoid loading entire file into RAM
        3. Has timeout protection (won't wait forever for slow servers)

        Why file size limit matters:
        Without this check, a malicious 10GB file could crash our server
        by filling up all available memory.
        """
        try:
            # SECURITY: Use stream=True to download in chunks, not all at once
            # This lets us check the file size in headers before committing to the full download
            r = self.session.get(document_url, stream=True, timeout=DOWNLOAD_TIMEOUT_SECONDS)

            if r.ok:
                # Check file size limit (default: 100MB)
                # Most meeting packets are 5-20MB, so 100MB catches outliers
                content_length = r.headers.get('Content-Length')
                if content_length and int(content_length) > MAX_FILE_SIZE_BYTES:
                    logger.warning(f"Skipping file: {document_url} is too large ({content_length} bytes, max: {MAX_FILE_SIZE_BYTES})")
                    return None
                return r
            else:
                # HTTP error (404, 500, etc.)
                return r.status_code
        except requests.RequestException as e:
            # Network errors: What can go wrong when downloading from the internet?
            # - Timeout: Server takes too long to respond (slow network, overloaded server)
            # - ConnectionError: Can't reach the server (network down, wrong URL)
            # - DNSError: Can't resolve domain name (typo in URL, DNS issues)
            # - TooManyRedirects: URL redirects in a loop
            # Why catch RequestException? It's the parent class for all requests errors
            logger.error(f"Request failed for {document_url}: {e}")
            return None

    def _store_document(self, response, content_type, url_hash):
        """
        Saves the downloaded content to the local disk.
        """
        file_path = self._create_fp_from_ocd_id(self.doc.ocd_division_id)
        
        # Determine the correct file extension
        if 'pdf' in content_type:
            ext = '.pdf'
        elif 'html' in content_type:
            ext = '.html'
        else:
            # Default to .pdf if unknown as most meeting docs are PDFs
            ext = '.pdf'

        full_path = os.path.join(file_path, f'{url_hash}{ext}')
        # Ensure we store the absolute path in the database
        abs_path = os.path.abspath(full_path)

        # Write the file in small chunks instead of loading it all into memory
        # Why chunk writing?
        # - A 20MB PDF loaded all at once = 20MB of RAM used
        # - A 20MB PDF written in 8KB chunks = only 8KB of RAM used at a time
        # This lets us handle large files without exhausting memory
        try:
            with open(abs_path, 'wb') as f:
                # iter_content() downloads and writes in small pieces
                for chunk in response.iter_content(chunk_size=FILE_WRITE_CHUNK_SIZE):
                    f.write(chunk)
            return abs_path
        except OSError as e:
            # File system errors: What can go wrong when writing to disk?
            # - PermissionError: No permission to write to this directory
            # - FileNotFoundError: Parent directory doesn't exist
            # - IsADirectoryError: Trying to write to a directory, not a file
            # - DiskFullError: No space left on disk
            # Why catch OSError? It's the parent class for all filesystem errors
            logger.error(f"Failed to write file {abs_path}: {e}")
            return None

    def _create_fp_from_ocd_id(self, ocd_id_str):
        """
        Creates a directory structure based on the location ID.
        Example: data/us/ca/belmont/
        """
        try:
            # Expected format: ocd-division/country:us/state:ca/place:belmont
            if not ocd_id_str or '/' not in ocd_id_str:
                raise ValueError("Missing '/' separator")
                
            parts = ocd_id_str.split('/')
            # Parts[0] is 'ocd-division', the rest are location segments
            # like ['country:us', 'state:ca', 'place:berkeley']
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
            # Path creation errors: What can go wrong when creating directories?
            # - ValueError: Malformed OCD-ID that can't be parsed into path segments
            # - OSError: Filesystem issues (permissions, invalid characters in path)
            # Why handle this? Some OCD-IDs from external sources might be malformed
            # Fallback strategy: Put it in a 'misc' folder rather than failing completely
            logger.warning(f"Malformed OCD-ID '{ocd_id_str}': {e}. Using fallback 'misc'.")
            fallback_path = os.path.join(self.working_dir, "misc")
            os.makedirs(fallback_path, exist_ok=True)
            return fallback_path


def process_single_url(url_record_id):
    """
    Processes a single URL from the staging table.
    Downloads the file, creates a Catalog entry, and links it to a Document.
    """
    engine = db_connect()
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Modern SQLAlchemy 2.0 way to fetch a record by its unique ID.
        url_record = session.get(UrlStage, url_record_id)
        if not url_record:
            return

        # Check if the meeting event exists in the main table.
        # We need an Event to link the document to.
        event_record = session.query(Event).filter(
            Event.ocd_division_id == url_record.ocd_division_id,
            Event.record_date == url_record.event_date,
            Event.name == url_record.event
        ).first()
        
        if not event_record:
            # If the event isn't found, we can't link the doc, so we skip it.
            logger.info(f"Skipping: Event not found for {url_record.event} ({url_record.event_date})")
            return

        # Check if we have already downloaded this file (by checking its hash).
        catalog_entry = session.query(Catalog).filter(
            Catalog.url_hash == url_record.url_hash
        ).first()

        if not catalog_entry:
            # It's a new file: Download it and add it to the Catalog.
            logger.info(f"Downloading new document: {url_record.url}")
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
                    session.flush() # Save immediately to get the ID
                except SQLAlchemyError:
                    # Race condition handling: What is a race condition?
                    # Two workers might try to download the same file simultaneously:
                    # 1. Worker A checks: "Does file X exist?" → No
                    # 2. Worker B checks: "Does file X exist?" → No
                    # 3. Worker A downloads and inserts record
                    # 4. Worker B tries to insert → DUPLICATE KEY ERROR!
                    # Solution: Catch the error, rollback, and re-fetch the record
                    # Why catch SQLAlchemyError? Covers all database errors (not just duplicates)
                    session.rollback()
                    catalog_entry = session.query(Catalog).filter(
                        Catalog.url_hash == url_record.url_hash
                    ).first()
            else:
                logger.error(f"Failed to download: {url_record.url}")
                return

        # Link the Document to the Event and the Catalog file.
        # Check if this link already exists to avoid duplicates.
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

    except SQLAlchemyError as e:
        # Database transaction errors: What can go wrong during a database transaction?
        # - IntegrityError: Violates a database constraint (duplicate key, foreign key)
        # - OperationalError: Database connection lost, server crashed
        # - DataError: Invalid data type (trying to store text in integer field)
        # - TimeoutError: Transaction took too long, database locked
        # Why rollback? If ANY part of the transaction fails, we undo ALL changes
        # to keep the database in a consistent state (atomicity principle)
        logger.error(f"Error processing URL record {url_record_id}: {e}")
        session.rollback()
    finally:
        session.close()


def process_staged_urls():
    """
    Main entry point for the downloader.

    What this does:
    1. Gets list of all URLs waiting to be downloaded
    2. Downloads them in parallel using multiple worker threads
    3. Saves files to disk and updates database

    Why parallel downloading?
    If we download one file at a time, a single slow server delays everything.
    By downloading multiple files simultaneously, we maximize throughput.
    """
    # Use context manager for automatic session cleanup
    with db_session() as session:
        # Get a list of all file IDs waiting to be downloaded
        url_ids = [r.id for r in session.query(UrlStage.id).all()]

    if not url_ids:
        logger.info("No URLs in staging table to process.")
        return

    logger.info(f"Processing {len(url_ids)} staged URLs using {DOWNLOAD_WORKERS} threads...")

    # Use parallel threads to speed up downloading multiple files at once
    # Why parallel? While one thread waits for a slow server, others can download from fast servers
    # DOWNLOAD_WORKERS controls how many files we download simultaneously (default: 5)
    with ThreadPoolExecutor(max_workers=DOWNLOAD_WORKERS) as executor:
        executor.map(process_single_url, url_ids)

    # After processing, move the records to the 'history' table so we don't process them again.
    archive_url_stage()


def archive_url_stage():
    """Moves processed records to the history table and clears staging."""
    engine = db_connect()
    with engine.begin() as conn:
        logger.info("Archiving processed URLs to history...")
        # Move data
        conn.execute(text("INSERT INTO url_stage_hist (ocd_division_id, event, event_date, url, url_hash, category, created_at) SELECT ocd_division_id, event, event_date, url, url_hash, category, created_at FROM url_stage"))
        # Clear staging
        conn.execute(text("DELETE FROM url_stage"))
        logger.info("Staging table cleared.")


if __name__ == "__main__":
    process_staged_urls()
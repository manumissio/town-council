import os
import requests
import logging
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker
from pipeline.models import Place, UrlStage, Event, Catalog, Document, UrlStageHist
from pipeline.models import db_connect, create_tables

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
        Includes safety checks for file size.
        """
        try:
            # Security: Use stream=True. This allows us to inspect the headers (like file size)
            # *before* downloading the entire huge file into memory.
            r = self.session.get(document_url, stream=True, timeout=30)
            
            if r.ok:
                # Check file size (limit to 100MB) to prevent crashing the server with massive files.
                content_length = r.headers.get('Content-Length')
                if content_length and int(content_length) > 104857600:
                    logger.warning(f"Skipping file: {document_url} is too large ({content_length} bytes)")
                    return None
                return r
            else:
                return r.status_code
        except Exception as e:
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

        # Write the file in chunks (8KB at a time).
        # This is much more memory efficient than loading the whole file into RAM at once.
        try:
            with open(abs_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            return abs_path
        except Exception as e:
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
            
        except Exception as e:
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
                except Exception:
                    # If someone else inserted it while we were downloading, re-fetch it
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

    except Exception as e:
        logger.error(f"Error processing URL record {url_record_id}: {e}")
        session.rollback()
    finally:
        session.close()


def process_staged_urls():
    """
    Main entry point for the downloader.
    Processes all URLs in the 'url_stage' table in parallel.
    """
    engine = db_connect()
    # Note: create_tables removed here as we expect DB to be initialized via db_init.py
    Session = sessionmaker(bind=engine)
    session = Session()

    # Get a list of all file IDs waiting to be downloaded.
    url_ids = [r.id for r in session.query(UrlStage.id).all()]
    session.close()

    if not url_ids:
        logger.info("No URLs in staging table to process.")
        return

    logger.info(f"Processing {len(url_ids)} staged URLs using 5 threads...")
    
    # Use 5 parallel threads to speed up downloading multiple files at once.
    with ThreadPoolExecutor(max_workers=5) as executor:
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
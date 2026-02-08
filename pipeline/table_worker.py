import os
import camelot
import json
import logging
from concurrent.futures import ProcessPoolExecutor, as_completed
from multiprocessing import cpu_count
from sqlalchemy.exc import SQLAlchemyError

from pipeline.models import Catalog
from pipeline.db_session import db_session
from pipeline.config import (
    TABLE_ACCURACY_MIN,
    TABLE_SCAN_MAX_PAGES,
    TABLE_WORKER_CPU_FRACTION,
    TABLE_PROGRESS_LOG_INTERVAL
)

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def process_single_pdf(catalog_id):
    """
    Worker function: Processes a single PDF for table extraction.

    What this does:
    1. Opens a PDF file and scans the first few pages
    2. Uses Camelot library to detect tables (grids of data)
    3. Extracts table data and saves it as JSON in the database

    Why separate processes?
    Python's GIL (Global Interpreter Lock) prevents true parallel threading.
    By using processes, each PDF gets its own Python interpreter = real parallelism.

    How Camelot works:
    - "lattice" mode: Looks for visible grid lines (like Excel tables)
    - "stream" mode: Detects alignment patterns (like text columns)
    - We try lattice first (more accurate), fallback to stream if needed
    """
    # Use context manager for automatic session cleanup and error handling
    with db_session() as session:
        try:
            record = session.get(Catalog, catalog_id)
            if not record or not os.path.exists(record.location):
                return 0

            # Only PDFs can contain structured tables
            # HTML documents use a different extraction method
            if not record.filename.lower().endswith('.pdf'):
                record.tables = []
                session.commit()
                return 1

            logger.info(f"Extracting tables from: {record.filename}")

            # DUAL-FLAVOR FALLBACK STRATEGY
            # Municipal tables usually appear in the first few pages (budgets, votes, etc.)
            # We scan only those pages for speed
            pages = f'1-{TABLE_SCAN_MAX_PAGES}'

            try:
                # Try lattice mode first (best for tables with visible borders)
                try:
                    tables = camelot.read_pdf(record.location, pages=pages, flavor='lattice')
                except (ValueError, OSError, RuntimeError, IndexError):
                    # PDF parsing errors: Why do we need a fallback strategy?
                    # Lattice mode can fail for several reasons:
                    # - ValueError: PDF has no grid lines (needs stream mode instead)
                    # - OSError: PDF is corrupted or unreadable
                    # - RuntimeError: Ghostscript (PDF renderer) failed
                    # - IndexError: PDF page tree is malformed or shorter than reported
                    # Solution: Try stream mode, which uses text alignment instead of lines
                    # Why catch these specific exceptions? Camelot uses different strategies
                    # that fail in predictable ways. We don't want to catch ALL errors here.
                    tables = camelot.read_pdf(record.location, pages=pages, flavor='stream')

                extracted_data = []
                for table in tables:
                    # Only keep high-confidence tables to avoid false positives
                    # Accuracy is a 0-100 score of how confident Camelot is
                    if table.accuracy > TABLE_ACCURACY_MIN:
                        df = table.df
                        # Convert DataFrame to list of lists (JSON-serializable)
                        # fillna("") replaces empty cells with empty strings
                        clean_data = df.fillna("").values.tolist()
                        extracted_data.append(clean_data)

                record.tables = extracted_data
                session.commit()
                return 1
            except (ValueError, OSError, RuntimeError, MemoryError, IndexError) as e:
                # Table extraction failures: What else can go wrong?
                # - ValueError: Invalid page range, malformed PDF structure
                # - OSError: File disappeared, permissions changed, disk full
                # - RuntimeError: Camelot's underlying libraries (Ghostscript, OpenCV) crashed
                # - MemoryError: PDF is too large (hundreds of pages with complex tables)
                # - IndexError: Parser cannot access a requested page in a broken PDF
                # Why mark as empty? Better to record "no tables found" than to keep
                # retrying the same broken PDF forever. Manual review can fix it later.
                logger.error(f"Final failure for {record.filename}: {e}")
                # If extraction fails, mark as empty rather than leaving as None
                # This prevents re-processing on next run
                record.tables = []
                session.commit()
                return 1

        except SQLAlchemyError as e:
            # Database errors in table extraction: What can go wrong with the database?
            # - IntegrityError: Trying to store invalid data (JSON too large)
            # - OperationalError: Database connection lost during long PDF processing
            # - DataError: Extracted tables contain characters the database can't store
            # Why catch separately? Database errors are different from PDF errors
            # The context manager will automatically rollback on exception
            logger.error(f"DB Error for {catalog_id}: {e}")
            return 0

def run_table_pipeline():
    """
    Orchestrates parallel table extraction across all PDFs.

    What this does:
    1. Finds all PDFs that need table extraction
    2. Spawns multiple worker processes to extract tables in parallel
    3. Each worker processes one PDF at a time

    Why parallel processing?
    Table extraction is CPU-intensive (image processing, OCR, line detection).
    By using multiple processes, we can extract from several PDFs simultaneously.

    Example: On a 4-core machine with 50% utilization = 2 workers
    - Sequential: 100 PDFs × 10 seconds = 1000 seconds (16.7 minutes)
    - Parallel (2 workers): 100 PDFs × 10 seconds ÷ 2 = 500 seconds (8.3 minutes)
    """
    # Use context manager for automatic session cleanup
    with db_session() as session:
        # Find documents needing table extraction
        # Skip placeholder records and already-processed documents
        to_process = session.query(Catalog).filter(
            Catalog.location != 'placeholder',
            Catalog.tables == None
        ).all()

        ids = [r.id for r in to_process]

    if not ids:
        logger.info("No documents need table extraction.")
        return

    logger.info(f"Starting parallel table extraction for {len(ids)} documents...")

    # Calculate optimal number of worker processes
    # Camelot is CPU-intensive, so we use a fraction of available cores
    # This keeps the system responsive for other tasks
    workers = max(1, int(cpu_count() * TABLE_WORKER_CPU_FRACTION))

    processed = 0
    # ProcessPoolExecutor creates separate Python processes (true parallelism)
    # Each process gets its own memory space and runs independently
    with ProcessPoolExecutor(max_workers=workers) as executor:
        # Submit all jobs to the executor
        # futures is a dictionary: {Future object: catalog_id}
        futures = {executor.submit(process_single_pdf, cid): cid for cid in ids}

        # Process results as they complete (not in submission order)
        # This gives us live progress updates
        for future in as_completed(futures):
            if future.result():
                processed += 1
                # Log progress periodically to track extraction without spamming logs
                if processed % TABLE_PROGRESS_LOG_INTERVAL == 0:
                    logger.info(f"Table Progress: {processed}/{len(ids)}")

if __name__ == "__main__":
    run_table_pipeline()

from concurrent.futures import ProcessPoolExecutor, as_completed
from multiprocessing import cpu_count
import logging
import sys
import subprocess
from sqlalchemy.exc import SQLAlchemyError

from pipeline.config import (
    DOCUMENT_CHUNK_SIZE,
    MAX_WORKERS,
    PIPELINE_CPU_FRACTION,
    DB_RETRY_DELAY_MIN,
    DB_RETRY_DELAY_MAX
)

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("pipeline-manager")

def run_step(name, command):
    """Helper to run a shell command step."""
    logger.info(f"Step: {name}")
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError:
        logger.error(f"Step {name} failed.")
        sys.exit(1)

def process_document_chunk(catalog_ids):
    """
    Worker function: Processes a CHUNK of documents using a single DB connection.

    What this does:
    1. Establishes ONE database connection for the entire chunk
    2. Processes 20 documents (or however many are in the chunk)
    3. For each document: extract text (if missing), then extract entities (if missing)
    4. Commits after each successful document

    Why chunk processing?
    Connection setup is expensive (~100ms per connection).
    Processing 1000 documents = 1000 connections = 100 seconds wasted!
    With chunks of 20: 1000 documents = 50 connections = 5 seconds.

    Why this runs in a separate process?
    This function is called by ProcessPoolExecutor, so it runs in its own
    Python interpreter. This enables true parallelism (no GIL limitation).

    Why custom retry logic?
    When multiple processes start simultaneously, they might overwhelm the
    database connection pool. Random retry delays prevent all workers from
    retrying at the same time (thundering herd problem).
    """
    from pipeline.models import db_connect, Catalog
    from pipeline.extractor import extract_text
    from pipeline.nlp_worker import extract_entities
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import text
    import time
    import random
    import sys

    # 1. Open connection ONCE for the entire batch
    # We retry with random backoff to avoid thundering herd
    db = None
    for attempt in range(3):
        try:
            engine = db_connect()
            Session = sessionmaker(bind=engine)
            db = Session()
            # Health check: verify the connection works
            db.execute(text("SELECT 1"))
            break
        except SQLAlchemyError:
            # Database connection errors: Why do connections fail during startup?
            # - Connection pool exhausted: All connections in use by other workers
            # - Database server restarting: Postgres/MySQL temporarily unavailable
            # - Network hiccup: Brief connectivity loss
            # - Authentication failure: Wrong credentials (rare in production)
            # Why retry with random delay? "Thundering herd" problem:
            #   If 10 workers all fail at once and retry at the same time,
            #   they'll all fail again! Random delays spread out the retries.
            if db: db.close()
            # Random delay prevents all workers from retrying simultaneously
            time.sleep(random.uniform(DB_RETRY_DELAY_MIN, DB_RETRY_DELAY_MAX))
            continue

    if not db:
        print(f"Error: Could not connect to database for chunk {catalog_ids[:2]}...", file=sys.stderr)
        return 0

    # 2. Process each document in the chunk
    processed_count = 0
    try:
        for cid in catalog_ids:
            catalog = db.get(Catalog, cid)
            if not catalog:
                continue

            # Text extraction (if missing)
            # This sends the PDF/HTML to Tika server
            if not catalog.content and catalog.location:
                catalog.content = extract_text(catalog.location)

            # NLP entity extraction (if missing)
            # This identifies people, organizations, and locations in the text
            if catalog.content and not catalog.entities:
                catalog.entities = extract_entities(catalog.content)

            # Commit after each document (incremental progress)
            # If we crash, we don't lose everything
            db.commit()
            processed_count += 1

        return processed_count
    except SQLAlchemyError as e:
        # Batch processing database errors: What can fail during document processing?
        # - IntegrityError: Duplicate key (another worker processed same document)
        # - OperationalError: Connection lost mid-batch (database crashed)
        # - DataError: Extracted content too large for database field
        # - StatementError: Invalid SQL generated (rare, likely a bug)
        # Why return processed_count? We successfully processed SOME documents
        # before the error. Better to save partial progress than lose everything.
        db.rollback()
        print(f"Error processing batch: {e}", file=sys.stderr)
        return processed_count
    finally:
        db.close()

def run_parallel_processing():
    """
    Orchestrates the parallel processing of documents in chunks.

    What this does:
    1. Finds all documents that need text extraction or entity extraction
    2. Splits them into manageable chunks (20 documents each)
    3. Spawns multiple worker processes to handle chunks in parallel
    4. Tracks progress as workers complete their chunks

    Why parallel processing?
    - Text extraction (Tika): I/O bound, waits on server responses
    - Entity extraction (NLP): CPU bound, processes text
    - By running multiple processes, we can extract from several documents
      simultaneously while some wait for Tika responses

    Performance example (4-core machine, 75% utilization = 3 workers):
    - Sequential: 300 docs × 10 seconds = 3000 seconds (50 minutes)
    - Parallel (3 workers): 300 docs × 10 seconds ÷ 3 = 1000 seconds (16.7 minutes)

    Why limit workers?
    The Tika server has limited resources. Too many parallel requests can
    overwhelm it, causing timeouts and failures. We cap at MAX_WORKERS to
    ensure stability.
    """
    from pipeline.models import Catalog
    from pipeline.db_session import db_session

    # Use context manager for automatic session cleanup
    with db_session() as db:
        # Find documents needing work (missing content OR missing entities)
        # Why OR? Some documents might have text but not entities yet
        unprocessed = db.query(Catalog).filter(
            (Catalog.content.is_(None)) | (Catalog.entities.is_(None))
        ).all()

        catalog_ids = [c.id for c in unprocessed]

    if not catalog_ids:
        logger.info("No documents need processing.")
        return

    # Split into chunks for batch processing
    # Why chunks? Each chunk reuses one DB connection for efficiency
    chunks = [catalog_ids[i:i + DOCUMENT_CHUNK_SIZE] for i in range(0, len(catalog_ids), DOCUMENT_CHUNK_SIZE)]

    logger.info(f"Starting parallel processing for {len(catalog_ids)} documents in {len(chunks)} chunks...")

    # Calculate optimal number of worker processes
    # Use a fraction of available CPUs, but cap at MAX_WORKERS
    cpu_limit = int(cpu_count() * PIPELINE_CPU_FRACTION)
    workers = max(1, min(cpu_limit, MAX_WORKERS))

    # ProcessPoolExecutor creates separate Python processes
    # Each process can run on a different CPU core (true parallelism)
    with ProcessPoolExecutor(max_workers=workers) as executor:
        # Submit all chunks to the executor
        # futures is a dictionary: {Future object: chunk data}
        futures = {executor.submit(process_document_chunk, chunk): chunk for chunk in chunks}

        # Track progress as chunks complete
        completed_docs = 0
        for future in as_completed(futures):
            count = future.result()
            if count:
                completed_docs += count
                logger.info(f"Progress: {completed_docs}/{len(catalog_ids)}")

def main():
    """
    Main pipeline entrypoint.
    """
    logger.info(">>> Starting High-Performance Pipeline")
    
    # 1. Setup & Ingest
    run_step("Seed Places", ["python", "seed_places.py"])
    run_step("Promote Staged Events", ["python", "promote_stage.py"])
    run_step("Downloader", ["python", "downloader.py"])
    
    # 2. Parallel Processing (Replaces extractor.py and nlp_worker.py)
    logger.info(">>> Starting Parallel Processing (OCR + NLP)")
    run_parallel_processing()
    
    # 3. Post-Processing
    # These steps depend on the global dataset, so they run sequentially after processing.
    run_step("Table Extraction", ["python", "table_worker.py"]) # Can fail safely
    run_step("Backfill Organizations", ["python", "backfill_orgs.py"])
    run_step("Topic Modeling", ["python", "topic_worker.py"])
    run_step("People Linking", ["python", "person_linker.py"])
    run_step("Search Indexing", ["python", "indexer.py"])
    
    logger.info("<<< Pipeline Complete")

if __name__ == "__main__":
    main()

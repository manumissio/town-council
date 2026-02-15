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
from pipeline.startup_purge import run_startup_purge_if_enabled

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
    Process a chunk of catalog IDs in one worker process.
    Reuses one DB session for the chunk and commits per document.
    """
    from pipeline.models import db_connect, Catalog
    from pipeline.extractor import extract_text
    from pipeline.content_hash import compute_content_hash
    from pipeline.nlp_worker import extract_entities
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import text
    import time
    import random
    import sys

    # Open one DB session for the chunk. Retry with jitter if DB is busy.
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
            if db: db.close()
            time.sleep(random.uniform(DB_RETRY_DELAY_MIN, DB_RETRY_DELAY_MAX))
            continue

    if not db:
        print(f"Error: Could not connect to database for chunk {catalog_ids[:2]}...", file=sys.stderr)
        return 0

    processed_count = 0
    try:
        for cid in catalog_ids:
            catalog = db.get(Catalog, cid)
            if not catalog:
                continue

            # Extract text only when needed.
            if not catalog.content and catalog.location:
                catalog.content = extract_text(catalog.location)
                catalog.content_hash = compute_content_hash(catalog.content)
            elif catalog.content and not getattr(catalog, "content_hash", None):
                # Older rows may predate content hashing.
                catalog.content_hash = compute_content_hash(catalog.content)

            # Extract entities only when needed.
            if catalog.content and not catalog.entities:
                catalog.entities = extract_entities(catalog.content)

            # Commit per document to keep partial progress.
            db.commit()
            processed_count += 1

        return processed_count
    except SQLAlchemyError as e:
        db.rollback()
        print(f"Error processing batch: {e}", file=sys.stderr)
        return processed_count
    finally:
        db.close()

def run_parallel_processing():
    """
    Find unprocessed docs and process them in parallel chunks.
    """
    from pipeline.models import Catalog
    from pipeline.db_session import db_session

    # Use context manager for automatic session cleanup
    with db_session() as db:
        # A document needs work if text or entities are missing.
        # Query IDs only: Catalog.content can be very large, and loading full rows
        # via .all() can spike RAM and crash the pipeline.
        unprocessed_ids = db.query(Catalog.id).filter(
            (Catalog.content.is_(None)) | (Catalog.entities.is_(None))
        ).yield_per(1000)

        catalog_ids = [row[0] for row in unprocessed_ids]

    if not catalog_ids:
        logger.info("No documents need processing.")
        return

    # Split IDs into fixed-size chunks.
    chunks = [catalog_ids[i:i + DOCUMENT_CHUNK_SIZE] for i in range(0, len(catalog_ids), DOCUMENT_CHUNK_SIZE)]

    logger.info(f"Starting parallel processing for {len(catalog_ids)} documents in {len(chunks)} chunks...")

    # Use a CPU fraction, capped for safety.
    cpu_limit = int(cpu_count() * PIPELINE_CPU_FRACTION)
    workers = max(1, min(cpu_limit, MAX_WORKERS))

    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(process_document_chunk, chunk): chunk for chunk in chunks}

        # Track completed documents across chunks.
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
    # Optional startup purge for derived fields. Safe to call repeatedly.
    purge_result = run_startup_purge_if_enabled()
    logger.info(f"startup_purge_result={purge_result}")
    
    # 1. Setup & Ingest
    # Keep dev databases compatible with the current SQLAlchemy models.
    run_step("DB Migrate", ["python", "db_migrate.py"])
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

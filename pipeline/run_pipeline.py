from concurrent.futures import ProcessPoolExecutor, as_completed
from multiprocessing import cpu_count
import logging
import sys
import subprocess

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
    This significantly reduces connection churn on Postgres.
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
    db = None
    for attempt in range(3):
        try:
            engine = db_connect()
            Session = sessionmaker(bind=engine)
            db = Session()
            db.execute(text("SELECT 1"))
            break
        except Exception:
            if db: db.close()
            time.sleep(random.uniform(1, 3))
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
                
            # OCR (if missing)
            if not catalog.content and catalog.location:
                catalog.content = extract_text(catalog.location)
                
            # NLP (if missing)
            if catalog.content and not catalog.entities:
                catalog.entities = extract_entities(catalog.content)
                
            db.commit()
            processed_count += 1
        return processed_count
    except Exception as e:
        db.rollback()
        print(f"Error processing batch: {e}", file=sys.stderr)
        return processed_count
    finally:
        db.close()

def run_parallel_processing():
    """
    Orchestrates the parallel processing of documents in chunks.
    """
    from pipeline.models import db_connect, Catalog
    from sqlalchemy.orm import sessionmaker
    
    engine = db_connect()
    Session = sessionmaker(bind=engine)
    db = Session()
    
    # Find documents needing work (missing content OR missing entities)
    unprocessed = db.query(Catalog).filter(
        (Catalog.content.is_(None)) | (Catalog.entities.is_(None))
    ).all()
    
    catalog_ids = [c.id for c in unprocessed]
    db.close()
    
    if not catalog_ids:
        logger.info("No documents need processing.")
        return

    # Split into chunks of 20
    chunk_size = 20
    chunks = [catalog_ids[i:i + chunk_size] for i in range(0, len(catalog_ids), chunk_size)]

    logger.info(f"Starting parallel processing for {len(catalog_ids)} documents in {len(chunks)} chunks...")
    
    # Use 75% of CPUs, but cap at 2 to avoid Tika server crashes
    # Note: OCR is extremely heavy; high concurrency on massive PDFs causes OOM.
    cpu_limit = int(cpu_count() * 0.75)
    workers = max(1, min(cpu_limit, 2))
    
    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(process_document_chunk, chunk): chunk for chunk in chunks}
        
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
    run_step("Topic Modeling", ["python", "topic_worker.py"])
    run_step("People Linking", ["python", "person_linker.py"])
    run_step("Search Indexing", ["python", "indexer.py"])
    
    logger.info("<<< Pipeline Complete")

if __name__ == "__main__":
    main()

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

def process_single_document(catalog_id):
    """
    Worker function: Processes a single document (OCR -> NLP).
    Runs in a separate process to bypass GIL.
    """
    # Import inside worker to avoid DB connection sharing issues
    from pipeline.models import db_connect, Catalog
    from pipeline.extractor import extract_text
    from pipeline.nlp_worker import extract_entities
    from sqlalchemy.orm import sessionmaker
    
    engine = db_connect()
    Session = sessionmaker(bind=engine)
    db = Session()
    
    try:
        catalog = db.get(Catalog, catalog_id)
        if not catalog:
            return None
            
        # 1. OCR (if missing)
        if not catalog.content and catalog.location:
            catalog.content = extract_text(catalog.location)
            
        # 2. NLP (if missing)
        if catalog.content and not catalog.entities:
            catalog.entities = extract_entities(catalog.content)
            
        db.commit()
        return catalog_id
    except Exception as e:
        db.rollback()
        # Log to stderr so parent process can capture if needed
        # (Logging in multiprocessing is tricky, simple print works for now)
        print(f"Error processing {catalog_id}: {e}", file=sys.stderr)
        return None
    finally:
        db.close()

def run_parallel_processing():
    """
    Orchestrates the parallel processing of documents.
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

    logger.info(f"Starting parallel processing for {len(catalog_ids)} documents...")
    
    # Use 75% of CPUs to leave room for DB/System
    workers = max(1, int(cpu_count() * 0.75))
    
    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(process_single_document, cid): cid for cid in catalog_ids}
        
        completed = 0
        for future in as_completed(futures):
            if future.result():
                completed += 1
                if completed % 10 == 0:
                    logger.info(f"Progress: {completed}/{len(catalog_ids)}")

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
import os
import camelot
import json
import logging
from concurrent.futures import ProcessPoolExecutor, as_completed
from multiprocessing import cpu_count
from sqlalchemy.orm import sessionmaker
from pipeline.models import Catalog, db_connect, create_tables

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def process_single_pdf(catalog_id):
    """
    Worker function: Processes a single PDF for table extraction.
    Runs in a separate process to bypass GIL and improve speed.
    """
    engine = db_connect()
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        record = session.get(Catalog, catalog_id)
        if not record or not os.path.exists(record.location):
            return 0

        # Only PDFs can contain structured tables.
        if not record.filename.lower().endswith('.pdf'):
            record.tables = []
            session.commit()
            return 1

        logger.info(f"Extracting tables from: {record.filename}")
        
        # DUAL-FLAVOR FALLBACK STRATEGY (Optimized for speed)
        # We only check the first 5 pages, as municipal tables usually appear early.
        try:
            try:
                tables = camelot.read_pdf(record.location, pages='1-5', flavor='lattice')
            except Exception:
                tables = camelot.read_pdf(record.location, pages='1-5', flavor='stream')
            
            extracted_data = []
            for table in tables:
                if table.accuracy > 70:
                    df = table.df
                    clean_data = df.fillna("").values.tolist()
                    extracted_data.append(clean_data)

            record.tables = extracted_data
            session.commit()
            return 1
        except Exception as e:
            logger.error(f"Final failure for {record.filename}: {e}")
            record.tables = []
            session.commit()
            return 1
            
    except Exception as e:
        logger.error(f"DB Error for {catalog_id}: {e}")
        session.rollback()
        return 0
    finally:
        session.close()

def run_table_pipeline():
    """
    Orchestrates parallel table extraction.
    """
    engine = db_connect()
    create_tables(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Find documents needing table extraction
    to_process = session.query(Catalog).filter(
        Catalog.location != 'placeholder',
        Catalog.tables == None
    ).all()
    
    ids = [r.id for r in to_process]
    session.close()

    if not ids:
        logger.info("No documents need table extraction.")
        return

    logger.info(f"Starting parallel table extraction for {len(ids)} documents...")
    
    # Camelot is CPU-intensive. Use 50% of cores to keep system responsive.
    workers = max(1, int(cpu_count() * 0.5))
    
    processed = 0
    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(process_single_pdf, cid): cid for cid in ids}
        
        for future in as_completed(futures):
            if future.result():
                processed += 1
                if processed % 10 == 0:
                    logger.info(f"Table Progress: {processed}/{len(ids)}")

if __name__ == "__main__":
    run_table_pipeline()
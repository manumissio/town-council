import sys
import os
import logging
import numpy as np
from sqlalchemy.orm import sessionmaker

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from pipeline.models import Catalog, db_connect

# Global availability for libraries
try:
    from sentence_transformers import SentenceTransformer
    import faiss
except ImportError:
    SentenceTransformer = None
    faiss = None

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("similarity-worker")

def run_similarity_engine():
    """
    Pre-calculates document similarities using Semantic Embeddings (AI Vectors).
    """
    # Use globals or local re-imports if mocked
    global SentenceTransformer, faiss
    
    if SentenceTransformer is None or faiss is None:
        # Check if they were mocked in sys.modules
        if 'sentence_transformers' in sys.modules:
            from sentence_transformers import SentenceTransformer
        if 'faiss' in sys.modules:
            import faiss
            
    if SentenceTransformer is None or faiss is None:
        logger.error("Missing required libraries: sentence-transformers, faiss-cpu.")
        return

    engine = db_connect()
    Session = sessionmaker(bind=engine)
    session = Session()

    # 1. Fetch documents that have content to compare
    logger.info("Fetching documents for semantic analysis...")
    records = session.query(Catalog).filter(
        Catalog.content != None,
        Catalog.content != ""
    ).all()

    if len(records) < 2:
        logger.warning("Not enough documents to calculate similarities.")
        session.close()
        return

    # 2. Prepare the Corpus (Text to analyze)
    corpus = []
    for r in records:
        text = r.summary or r.summary_extractive or r.content[:5000]
        corpus.append(text)

    # 3. Load the AI Model
    logger.info("Loading sentence-transformer model (all-MiniLM-L6-v2)...")
    model = SentenceTransformer('all-MiniLM-L6-v2')

    # 4. Generate Embeddings
    logger.info(f"Generating embeddings for {len(records)} documents...")
    embeddings = model.encode(corpus, batch_size=32, show_progress_bar=False)

    # 5. Normalize and Index
    faiss.normalize_L2(embeddings)
    
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatIP(dimension)
    index.add(embeddings)

    # 6. Search for top 4 neighbors (includes self)
    distances, indices = index.search(embeddings, 4)

    # 7. Update Catalog records
    for i, record in enumerate(records):
        top_related_ids = []
        for j, neighbor_idx in enumerate(indices[i]):
            if neighbor_idx == i:
                continue
            
            # score > 0.35
            if distances[i][j] < 0.35:
                continue
                
            top_related_ids.append(records[neighbor_idx].id)
            if len(top_related_ids) >= 3:
                break
                
        record.related_ids = top_related_ids

    # 8. Commit changes
    try:
        session.commit()
        logger.info(f"Semantic linking complete. Processed {len(records)} documents.")
    except Exception as e:
        logger.error(f"Failed to save semantic links: {e}")
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    run_similarity_engine()

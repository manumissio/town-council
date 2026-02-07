import sys
import os
import logging
import numpy as np
from sqlalchemy.orm import sessionmaker

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from pipeline.models import Catalog, db_connect, create_tables

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("similarity-worker")

def run_similarity_engine():
    """
    Pre-calculates document similarities using Semantic Embeddings (AI Vectors).
    
    Why: Instead of just matching keywords (TF-IDF), this system understands 
    concepts. Searching for 'housing' will now find meetings about 'zoning' 
    or 'residential development' because their mathematical 'vectors' are similar.
    
    Novice Developer Note:
    1. Every document is turned into a list of 384 numbers (an Embedding).
    2. We store these numbers in a 'FAISS Index' (a super-fast search engine).
    3. We ask the index: "For Meeting A, what are the top 3 closest other meetings?"
    """
    
    # We import these inside the function to avoid loading heavy AI models 
    # if the script is just being imported by another file.
    try:
        from sentence_transformers import SentenceTransformer
        import faiss
    except ImportError:
        logger.error("Missing required libraries: sentence-transformers, faiss-cpu. Run pip install.")
        return

    engine = db_connect()
    create_tables(engine)
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
        return

    # 2. Prepare the Corpus (Text to analyze)
    # We prioritize the summary if it exists, as it contains the most 'dense' meaning.
    corpus = []
    for r in records:
        text = r.summary or r.summary_extractive or r.content[:5000]
        corpus.append(text)

    # 3. Load the AI Model (The 'Brain')
    # all-MiniLM-L6-v2 is a lightweight but powerful model for English.
    logger.info("Loading sentence-transformer model (all-MiniLM-L6-v2)...")
    model = SentenceTransformer('all-MiniLM-L6-v2')

    # 4. Generate Embeddings (Turning text into numbers)
    # show_progress_bar=True helps us see how long it will take.
    logger.info(f"Generating embeddings for {len(records)} documents...")
    embeddings = model.encode(corpus, batch_size=32, show_progress_bar=False)
    
    # Normalize the vectors. 
    # This makes 'Inner Product' (IP) search equivalent to 'Cosine Similarity'.
    faiss.normalize_L2(embeddings)

    # 5. Build the FAISS Index (The Search Engine)
    dimension = embeddings.shape[1] # For this model, it's 384
    index = faiss.IndexFlatIP(dimension)
    index.add(embeddings.astype('float32'))

    # 6. Find the top 4 matches for every document
    # We ask for 4 because the #1 match is always the document itself.
    logger.info("Searching for related meetings...")
    distances, indices = index.search(embeddings.astype('float32'), 4)

    # 7. Save the matches back to the database
    for i, record in enumerate(records):
        top_related_ids = []
        
        # indices[i] contains the positions of the top 4 matches
        # distances[i] contains their similarity scores (0.0 to 1.0)
        for j, neighbor_idx in enumerate(indices[i]):
            # Skip the first match (the document matching itself)
            if neighbor_idx == i:
                continue
            
            # Security/Quality Check: Only link if they are actually similar (score > 0.35)
            # 1.0 is a perfect match, 0.0 is completely different.
            if distances[i][j] < 0.35:
                continue
                
            top_related_ids.append(records[neighbor_idx].id)
            
            # Stop once we have 3 related meetings
            if len(top_related_ids) >= 3:
                break
                
        record.related_ids = top_related_ids

    # 8. Commit changes to the database
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
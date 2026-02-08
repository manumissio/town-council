import sys
import os
import logging
import numpy as np

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from pipeline.models import Catalog
from pipeline.db_session import db_session
from pipeline.config import (
    SIMILARITY_CONTENT_LENGTH,
    EMBEDDING_BATCH_SIZE,
    SIMILARITY_THRESHOLD,
    FAISS_TOP_NEIGHBORS,
    MAX_RELATED_DOCS
)

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

    What this does:
    1. Converts each meeting document into a mathematical vector (embedding)
    2. Uses AI to find which documents are semantically similar
    3. Links related documents together for "you might also like" features

    What are embeddings?
    An embedding is a list of numbers that represents the "meaning" of text.
    Documents with similar meanings have similar numbers.

    How it works:
    - "Public Housing Project" and "Affordable Housing Initiative" get similar vectors
    - "Traffic Study" and "Bike Lane Proposal" get different vectors
    - We use cosine similarity to measure how close vectors are (0-1 scale)
    """
    # Use globals or local re-imports if mocked (for testing)
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

    # Use context manager for automatic session cleanup and error handling
    with db_session() as session:
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
        # We prefer summaries (shorter, more focused) over raw content
        corpus = []
        for r in records:
            # Use AI summary if available, fallback to extractive summary,
            # then fallback to first portion of content
            text = r.summary or r.summary_extractive or r.content[:SIMILARITY_CONTENT_LENGTH]
            corpus.append(text)

        # 3. Load the AI Model
        # all-MiniLM-L6-v2 is a lightweight model that's fast and accurate
        # It converts sentences into 384-dimensional vectors
        logger.info("Loading sentence-transformer model (all-MiniLM-L6-v2)...")
        model = SentenceTransformer('all-MiniLM-L6-v2')

        # 4. Generate Embeddings
        # This is the slow part: converting text into mathematical vectors
        # Processing in batches speeds this up significantly
        logger.info(f"Generating embeddings for {len(records)} documents...")
        embeddings = model.encode(corpus, batch_size=EMBEDDING_BATCH_SIZE, show_progress_bar=False)

        # 5. Normalize and Index with FAISS
        # Normalization ensures all vectors have length=1 (unit vectors)
        # This lets us use Inner Product (IP) search, which is fast
        faiss.normalize_L2(embeddings)

        # Create a FAISS index (a database for fast vector search)
        # IndexFlatIP = "Flat" (exact search, not approximate) + "IP" (Inner Product)
        dimension = embeddings.shape[1]
        index = faiss.IndexFlatIP(dimension)
        index.add(embeddings)

        # 6. Search for nearest neighbors
        # For each document, find the most similar documents
        # We fetch the top N neighbors (includes the document itself)
        distances, indices = index.search(embeddings, FAISS_TOP_NEIGHBORS)

        # 7. Update Catalog records with related document IDs
        for i, record in enumerate(records):
            top_related_ids = []

            # Loop through the neighbors for this document
            for j, neighbor_idx in enumerate(indices[i]):
                # Skip self-similarity (a document is always most similar to itself)
                if neighbor_idx == i:
                    continue

                # Only keep documents above the similarity threshold
                # Lower scores = less similar, so we skip them
                if distances[i][j] < SIMILARITY_THRESHOLD:
                    continue

                top_related_ids.append(records[neighbor_idx].id)

                # Stop after finding enough related documents
                if len(top_related_ids) >= MAX_RELATED_DOCS:
                    break

            record.related_ids = top_related_ids

        # 8. Commit changes
        # The context manager will automatically rollback if this fails
        session.commit()
        logger.info(f"Semantic linking complete. Processed {len(records)} documents.")

if __name__ == "__main__":
    run_similarity_engine()

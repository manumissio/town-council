import os
import sys
import time
import spacy
import pytextrank
import threading

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from pipeline.models import Catalog
from pipeline.db_session import db_session
from pipeline.config import MAX_SUMMARY_TEXT_LENGTH

# Global cache for the NLP model to avoid reloading in the same process
# What's a cache? It's a stored copy that we reuse instead of recreating
# Loading the model takes ~2 seconds, so we only want to do it once
_cached_nlp_rank = None
_model_lock = threading.Lock()  # Prevents race conditions when loading model

def get_summarization_model():
    """
    Returns a SpaCy model with TextRank initialized.

    What is TextRank?
    It's an algorithm that finds the most important sentences in a document.
    Think of it like highlighting the key points in a textbook.
    """
    global _cached_nlp_rank

    # Fast path: if model is already loaded, return it immediately
    if _cached_nlp_rank:
        return _cached_nlp_rank

    # Thread-safe model loading
    # The lock ensures only one thread loads the model at a time
    with _model_lock:
        # Double-check after acquiring lock (another thread might have loaded it while we waited)
        if _cached_nlp_rank:
            return _cached_nlp_rank

        try:
            # Load SpaCy's small English model (~13MB)
            nlp = spacy.load("en_core_web_sm")
            # Add TextRank pipeline for extractive summarization
            nlp.add_pipe("textrank")
            _cached_nlp_rank = nlp
            return nlp
        except Exception as e:
            print(f"Error loading NLP model for summarization: {e}")
            return None

def extract_summarize_catalog(catalog_id):
    """
    Performs Tier 1 (Extractive) summarization on a single catalog record.

    What's extractive summarization?
    Instead of generating new text (like AI), it selects the most important
    sentences that already exist in the document. Faster and more reliable.
    """
    nlp = get_summarization_model()
    if not nlp: return

    # Use context manager for automatic session cleanup
    with db_session() as session:
        catalog = session.get(Catalog, catalog_id)
        if not catalog or not catalog.content:
            return

        # PERFORMANCE: Only process the first portion of the text
        # Why truncate? TextRank gets slower with more text, and key points
        # are usually in the beginning of meeting documents anyway
        doc = nlp(catalog.content[:MAX_SUMMARY_TEXT_LENGTH])
        
        limit_phrases = 10
        limit_sentences = 3
        
        summary_sentences = []
        for sent in doc._.textrank.summary(limit_phrases=limit_phrases, limit_sentences=limit_sentences):
            summary_sentences.append(sent.text.replace("\n", " ").strip())
        
        if summary_sentences:
            # Join the selected sentences into a single summary
            catalog.summary_extractive = " ".join(summary_sentences)
            session.commit()

        # No need for except/finally - the context manager handles:
        # - Automatic rollback if an exception occurs
        # - Automatic session close when we exit the "with" block

def summarize_documents():
    """
    Legacy batch processing function.
    """
    engine = db_connect()
    Session = sessionmaker(bind=engine)
    session = Session()

    to_summarize = session.query(Catalog).filter(
        Catalog.content != None,
        Catalog.content != "",
        Catalog.summary_extractive == None
    ).limit(50).all()

    ids = [c.id for c in to_summarize]
    session.close()

    for cid in ids:
        extract_summarize_catalog(cid)

if __name__ == "__main__":
    summarize_documents()

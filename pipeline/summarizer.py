import os
import sys
import time
import spacy
import pytextrank
from sqlalchemy.orm import sessionmaker

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from pipeline.models import Catalog, db_connect, create_tables

# Global cache for the NLP model to avoid reloading in the same process
_cached_nlp_rank = None

def get_summarization_model():
    """
    Returns a SpaCy model with TextRank initialized.
    """
    global _cached_nlp_rank
    if _cached_nlp_rank:
        return _cached_nlp_rank
        
    try:
        nlp = spacy.load("en_core_web_sm")
        nlp.add_pipe("textrank")
        _cached_nlp_rank = nlp
        return nlp
    except Exception as e:
        print(f"Error loading NLP model for summarization: {e}")
        return None

def extract_summarize_catalog(catalog_id):
    """
    Performs Tier 1 (Extractive) summarization on a single catalog record.
    """
    nlp = get_summarization_model()
    if not nlp: return

    engine = db_connect()
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        catalog = session.get(Catalog, catalog_id)
        if not catalog or not catalog.content:
            return

        # PERFORMANCE: Only summarize the first 50k characters.
        doc = nlp(catalog.content[:50000])
        
        limit_phrases = 10
        limit_sentences = 3
        
        summary_sentences = []
        for sent in doc._.textrank.summary(limit_phrases=limit_phrases, limit_sentences=limit_sentences):
            summary_sentences.append(sent.text.replace("\n", " ").strip())
        
        if summary_sentences:
            catalog.summary_extractive = " ".join(summary_sentences)
            session.commit()
    except Exception as e:
        print(f"Error in extractive summarization: {e}")
        session.rollback()
    finally:
        session.close()

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

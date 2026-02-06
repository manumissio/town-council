import sys
import os
import logging
import numpy as np
from sqlalchemy.orm import sessionmaker
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from pipeline.models import Catalog, db_connect, create_tables

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("similarity-worker")

# Reusing the same stop words to ensure consistent 'meaning' extraction
CITY_STOP_WORDS = [
    "meeting", "council", "city", "minutes", "present", "absent", "motion", 
    "seconded", "voted", "item", "resolution", "ordinance", "approved", 
    "unanimous", "quorum", "adjourned", "p.m.", "a.m.", "january", "february",
    "march", "april", "may", "june", "july", "august", "september", "october",
    "november", "december", "monday", "tuesday", "wednesday", "thursday", 
    "friday", "hereby", "thereof", "therein", "clerk", "mayor", "councilmember",
    "commissioner", "staff", "report", "public", "comment", "called", "order",
    "action", "discussion", "held", "carried", "aye", "noes", "abstain"
]

def run_similarity_engine():
    """
    Pre-calculates document similarities using TF-IDF and Cosine Similarity.
    
    Why: Finding 'Related Meetings' on-the-fly is slow. By pre-calculating the 
    top matches and storing them in the DB, the UI can show them instantly.
    """
    engine = db_connect()
    create_tables(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # 1. Fetch documents that have enough text to compare
    logger.info("Fetching documents for similarity analysis...")
    records = session.query(Catalog).filter(
        Catalog.content != None,
        Catalog.content != ""
    ).all()

    if len(records) < 2:
        logger.warning("Not enough documents to calculate similarities.")
        return

    # 2. Build the corpus using a mix of summaries and content for 'Meaning Density'
    # We prefer the summaries because they contain the most important topics.
    corpus = []
    for r in records:
        text_source = f"{r.summary or ''} {r.summary_extractive or ''} {r.content[:10000]}"
        corpus.append(text_source)

    # 3. Vectorize the entire database
    # Junior Dev Note: This turns every document into a list of numbers (a Vector).
    vectorizer = TfidfVectorizer(
        stop_words=CITY_STOP_WORDS,
        max_df=0.7,
        min_df=1,
        max_features=10000
    )
    
    try:
        tfidf_matrix = vectorizer.fit_transform(corpus)
        # 4. Calculate the 'Distance' between every document
        # result is a square matrix where similarity[i][j] is the score between doc i and j.
        similarity_matrix = cosine_similarity(tfidf_matrix)
    except Exception as e:
        logger.error(f"Similarity math failed: {e}")
        return

    # 5. Find the top 3 related documents for each record
    logger.info(f"Linking {len(records)} documents...")
    for i, record in enumerate(records):
        # Get similarities for this specific document
        scores = similarity_matrix[i]
        
        # Sort indices by score (highest first)
        # We exclude the first one because it's always the document itself (score 1.0)
        related_indices = scores.argsort()[::-1]
        
        top_related_ids = []
        for idx in related_indices:
            if idx == i: continue # Skip self
            
            # Stop if the score is too low (meaning they aren't actually related)
            if scores[idx] < 0.1: break 
            
            top_related_ids.append(records[idx].id)
            
            if len(top_related_ids) >= 3: break # Limit to 3 related meetings
            
        record.related_ids = top_related_ids

    # 6. Save back to database
    try:
        session.commit()
        logger.info("Similarity linking complete.")
    except Exception as e:
        logger.error(f"Failed to save related links: {e}")
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    run_similarity_engine()

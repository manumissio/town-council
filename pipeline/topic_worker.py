import sys
import os
import logging
from sqlalchemy.orm import sessionmaker
from sklearn.feature_extraction.text import TfidfVectorizer

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from pipeline.models import Catalog, db_connect, create_tables

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("topic-worker")

# MUNICIPAL STOP WORDS
# These are words that appear constantly in city documents but aren't useful as 'Topics'.
# We filter these out so they don't drown out real topics like 'Housing' or 'Biking'.
CITY_STOP_WORDS = [
    "meeting", "council", "city", "minutes", "present", "absent", "motion", 
    "seconded", "voted", "item", "resolution", "ordinance", "approved", 
    "unanimous", "quorum", "adjourned", "p.m.", "a.m.", "january", "february",
    "march", "april", "may", "june", "july", "august", "september", "october",
    "november", "december", "monday", "tuesday", "wednesday", "thursday", 
    "friday", "hereby", "thereof", "therein", "clerk", "mayor", "councilmember",
    "commissioner", "staff", "report", "public", "comment", "called", "order",
    "action", "discussion", "held", "held", "carried", "aye", "noes", "abstain"
]

def run_keyword_tagger():
    """
    Alias for run_topic_tagger to match test expectations.
    """
    run_topic_tagger()

def run_topic_tagger():
    """
    Automated Topic Discovery using TF-IDF.
    """
    engine = db_connect()
    # Note: create_tables removed from worker, assumed done via db_init.py
    Session = sessionmaker(bind=engine)
    session = Session()

    # 1. Fetch all documents that have text
    logger.info("Fetching documents for topic analysis...")
    records = session.query(Catalog).filter(
        Catalog.content != None,
        Catalog.content != ""
    ).all()

    # Pre-initialize topics to empty lists
    for r in records:
        r.topics = []

    if len(records) < 2:
        logger.warning("Not enough documents to perform TF-IDF analysis.")
        session.commit()
        return

    # 2. Prepare the corpus (the list of all text)
    # We limit to first 50k characters for performance.
    corpus = [r.content[:50000] for r in records]
    filenames = [r.filename for r in records]

    logger.info(f"Analyzing {len(corpus)} documents...")

    # 3. Setup the TF-IDF Vectorizer
    # max_df=0.8 means 'ignore words that appear in more than 80% of documents' (too common)
    # min_df=2 means 'ignore words that only appear in 1 document' (too rare/typos)
    vectorizer = TfidfVectorizer(
        stop_words=CITY_STOP_WORDS,
        max_df=0.8,
        min_df=1, # Allow unique topics even in small datasets
        max_features=5000, # Only track the top 5000 most common words globally
        ngram_range=(1, 2) # Catch single words ('Housing') and phrases ('Rent Control')
    )

    try:
        tfidf_matrix = vectorizer.fit_transform(corpus)
        feature_names = vectorizer.get_feature_names_out()
    except Exception as e:
        logger.error(f"TF-IDF math failed: {e}")
        session.commit()
        return

    # 4. Extract top 5 keywords for each document
    for i, record in enumerate(records):
        # Initialize to empty list
        record.topics = []
        
        try:
            # Get the scores for this specific document
            doc_vector = tfidf_matrix[i].toarray()[0]
            
            # Sort words by their score (highest first)
            top_indices = doc_vector.argsort()[-5:][::-1]
            
            # Only keep words with a score > 0 (meaning they actually appeared)
            keywords = [feature_names[idx] for idx in top_indices if doc_vector[idx] > 0]
            
            # Clean up: Capitalize for the UI
            record.topics = [k.title() for k in keywords]
        except Exception:
            # If a specific doc fails (e.g. only stop words), it just gets no topics
            continue
        
        if i % 50 == 0:
            logger.info(f"Processed {i}/{len(records)} documents...")

    # 5. Save all new topics to the database
    try:
        session.commit()
        logger.info("Topic tagging complete and saved to database.")
    except Exception as e:
        logger.error(f"Failed to save topics: {e}")
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    run_topic_tagger()

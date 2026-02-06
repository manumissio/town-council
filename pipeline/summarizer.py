import os
import sys
import time
import spacy
import pytextrank
from google import genai
from sqlalchemy.orm import sessionmaker

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from pipeline.models import Catalog, db_connect, create_tables

def summarize_documents():
    """
    Hybrid Summarization Engine:
    
    1. Tier 1 (Fast Pass): Uses TextRank (Traditional AI) to instantly pick the 3 most 
       important sentences from the text for $0.
    2. Tier 2 (Deep Pass): Uses Gemini (LLM) to write a polished 3-bullet summary.
       Note: Tier 2 is often triggered on-demand via the UI.
    """
    print("Loading SpaCy NLP model for summarization...")
    try:
        # Load SpaCy and add PyTextRank to the pipeline
        nlp = spacy.load("en_core_web_sm")
        nlp.add_pipe("textrank")
    except Exception as e:
        print(f"Error loading NLP model: {e}")
        return

    engine = db_connect()
    create_tables(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Find documents that need an extractive summary (Tier 1)
    to_summarize = session.query(Catalog).filter(
        Catalog.content != None,
        Catalog.content != "",
        Catalog.summary_extractive == None
    ).limit(50).all() # Process in batches of 50

    print(f"Found {len(to_summarize)} documents for Extractive Summarization (Tier 1).")

    for record in to_summarize:
        try:
            # PERFORMANCE: Only summarize the first 50k characters.
            # Meeting records are huge, and the most important info is usually at the top.
            text_to_process = record.content[:50000]
            
            doc = nlp(text_to_process)
            
            # Extract top 3 sentences based on TextRank score
            # TextRank is like Google's PageRank but for sentences. It finds the "center" of the discussion.
            sent_bounds = [ [s.start, s.end, s.text.replace("\n", " ").strip()] for s in doc.sents ]
            
            limit_phrases = 10
            limit_sentences = 3
            
            summary_sentences = []
            for sent in doc._.textrank.summary(limit_phrases=limit_phrases, limit_sentences=limit_sentences):
                summary_sentences.append(sent.text.replace("\n", " ").strip())
            
            if summary_sentences:
                # Combine into a single text block
                record.summary_extractive = " ".join(summary_sentences)
                session.commit()
                print(f"Tier 1 Summary saved for: {record.filename}")
            
        except Exception as e:
            print(f"Error in Tier 1 summarization for {record.filename}: {e}")
            session.rollback()

    session.close()
    print("Summarization process complete.")

if __name__ == "__main__":
    summarize_documents()

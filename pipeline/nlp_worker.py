import time
import spacy
from sqlalchemy.orm import sessionmaker
from models import Catalog, db_connect, create_tables

def run_nlp_pipeline():
    """
    Scans for documents that have text content but no extracted entities.
    Uses SpaCy (NER) to identify Organizations and Locations within the text.
    """
    print("Loading SpaCy NLP model (en_core_web_sm)...")
    try:
        # Disable components we don't need (parser, lemmatizer) for speed
        nlp = spacy.load("en_core_web_sm", disable=["parser", "lemmatizer"])
    except OSError:
        print("Error: SpaCy model 'en_core_web_sm' not found. Ensure it is installed.")
        return

    engine = db_connect()
    create_tables(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Find documents with text but no entities extracted yet
    to_process = session.query(Catalog).filter(
        Catalog.content != None,
        Catalog.content != "",
        Catalog.entities == None
    ).all()

    print(f"Found {len(to_process)} documents for NLP processing.")

    # Process in batches using SpaCy's efficient pipe
    # We yield (doc_id, text) pairs so we can map results back to records
    # Limit text length to 100k chars to prevent memory issues with massive PDFs
    doc_tuples = [(record, record.content[:100000]) for record in to_process]
    
    for record, spacy_doc in zip([r for r, t in doc_tuples], 
                                 nlp.pipe([t for r, t in doc_tuples], batch_size=20)):
        
        entities = {
            "orgs": [],
            "locs": [],
            "persons": []
        }

        # Extract and categorize entities
        for ent in spacy_doc.ents:
            # Clean up the entity text
            text = ent.text.strip().replace('
', ' ')
            
            if len(text) < 2 or len(text) > 100:
                continue

            if ent.label_ == "ORG" and text not in entities["orgs"]:
                entities["orgs"].append(text)
            elif ent.label_ in ["GPE", "LOC"] and text not in entities["locs"]:
                entities["locs"].append(text)
            elif ent.label_ == "PERSON" and text not in entities["persons"]:
                entities["persons"].append(text)

        # Store result as JSON
        record.entities = entities
        print(f"Processed {record.filename}: Found {len(entities['orgs'])} Orgs, {len(entities['locs'])} Locs")

    # Commit all changes
    try:
        session.commit()
        print("NLP processing complete and saved to database.")
    except Exception as e:
        print(f"Error saving to database: {e}")
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    run_nlp_pipeline()

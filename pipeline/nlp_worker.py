import sys
import os
import time
import spacy
from sqlalchemy.orm import sessionmaker

# Add project root to path for consistent imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from pipeline.models import Catalog, db_connect, create_tables
from pipeline.utils import is_likely_human_name

def get_municipal_nlp_model():
    """
    Creates an NLP model customized for municipal documents.
    Adds a 'RuleRuler' with deterministic patterns to catch names 
    that generic AI models often miss.
    """
    # Load the base English model.
    nlp = spacy.load("en_core_web_sm", disable=["parser", "lemmatizer"])
    
    # Create the EntityRuler. 
    # This allows us to define 'Rules' that the AI must follow.
    ruler = nlp.add_pipe("entity_ruler", before="ner")
    
    # Define custom municipal patterns.
    # Junior Dev Note: 'patterns' are simple rules. 
    # e.g., If you see the word 'Mayor', the next few capitalized words are a PERSON.
    patterns = [
        # Titles: Catch people based on their role
        {"label": "PERSON", "pattern": [{"LOWER": "mayor"}, {"IS_TITLE": True}]},
        {"label": "PERSON", "pattern": [{"LOWER": "mayor"}, {"IS_TITLE": True}, {"IS_TITLE": True}]},
        {"label": "PERSON", "pattern": [{"LOWER": "councilmember"}, {"IS_TITLE": True}]},
        {"label": "PERSON", "pattern": [{"LOWER": "councilmember"}, {"IS_TITLE": True}, {"IS_TITLE": True}]},
        {"label": "PERSON", "pattern": [{"LOWER": "commissioner"}, {"IS_TITLE": True}]},
        {"label": "PERSON", "pattern": [{"LOWER": "commissioner"}, {"IS_TITLE": True}, {"IS_TITLE": True}]},
        {"label": "PERSON", "pattern": [{"LOWER": "chair"}, {"IS_TITLE": True}]},
        {"label": "PERSON", "pattern": [{"LOWER": "chair"}, {"IS_TITLE": True}, {"IS_TITLE": True}]},
        {"label": "PERSON", "pattern": [{"LOWER": "director"}, {"IS_TITLE": True}]},
        {"label": "PERSON", "pattern": [{"LOWER": "director"}, {"IS_TITLE": True}, {"IS_TITLE": True}]},
        
        # Motion Workflow: Catch who is moving and seconding items
        {"label": "PERSON", "pattern": [{"LOWER": "moved"}, {"LOWER": "by"}, {"IS_TITLE": True}]},
        {"label": "PERSON", "pattern": [{"LOWER": "moved"}, {"LOWER": "by"}, {"IS_TITLE": True}, {"IS_TITLE": True}]},
        {"label": "PERSON", "pattern": [{"LOWER": "seconded"}, {"LOWER": "by"}, {"IS_TITLE": True}]},
        {"label": "PERSON", "pattern": [{"LOWER": "seconded"}, {"LOWER": "by"}, {"IS_TITLE": True}, {"IS_TITLE": True}]},
        
        # Vote Blocks
        {"label": "PERSON", "pattern": [{"LOWER": "ayes"}, {"ORTH": ":"}, {"IS_TITLE": True}]},
        {"label": "PERSON", "pattern": [{"LOWER": "noes"}, {"ORTH": ":"}, {"IS_TITLE": True}]},
    ]
    
    ruler.add_patterns(patterns)
    return nlp

def run_nlp_pipeline():
    """
    Scans meeting minutes to automatically identify important names.
    
    How it works (Named Entity Recognition):
    1. It loads a CUSTOMIZED language model (SpaCy + RuleRuler).
    2. It reads documents that haven't been analyzed yet.
    3. It finds and categorizes names of Organizations (ORG) and People (PERSON).
    4. It saves these lists to the database.
    """
    print("Loading Customized Municipal NLP model...")
    nlp = get_municipal_nlp_model()

    engine = db_connect()
    create_tables(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Find documents that have text content but haven't been processed for entities yet.
    to_process = session.query(Catalog).filter(
        Catalog.content != None,
        Catalog.content != "",
        Catalog.entities == None
    ).all()

    print(f"Found {len(to_process)} documents for NLP processing.")

    # Process documents in batches for better performance.
    doc_tuples = [(record, record.content[:100000]) for record in to_process]
    
    for record, spacy_doc in zip([r for r, t in doc_tuples], 
                                 nlp.pipe([t for r, t in doc_tuples], batch_size=20)):
        
        entities = {
            "orgs": [],
            "locs": [],
            "persons": []
        }

        for ent in spacy_doc.ents:
            text = ent.text.strip().replace('\n', ' ')
            
            # Remove leading trigger words (e.g., 'Moved by ' or 'Mayor ')
            # This ensures we only store the actual name in the database.
            triggers = ["moved by", "seconded by", "mayor", "councilmember", "commissioner", "chair", "director", "ayes :", "noes :"]
            for trigger in triggers:
                if text.lower().startswith(trigger):
                    text = text[len(trigger):].strip()
            
            if len(text) < 2 or len(text) > 100:
                continue

            # Validation: Use our strict name validator to skip junk like "Teleconference Location"
            if ent.label_ == "PERSON":
                if not is_likely_human_name(text):
                    continue
                if text not in entities["persons"]:
                    entities["persons"].append(text)
            
            elif ent.label_ == "ORG" and text not in entities["orgs"]:
                entities["orgs"].append(text)
            
            elif ent.label_ in ["GPE", "LOC"] and text not in entities["locs"]:
                entities["locs"].append(text)

        # Save the results as a JSON object in the database.
        record.entities = entities
        print(f"Processed {record.filename}: Found {len(entities['persons'])} People")

    # Save changes
    try:
        session.commit()
        print("NLP processing complete.")
    except Exception as e:
        print(f"Error saving to database: {e}")
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    run_nlp_pipeline()

if __name__ == "__main__":
    run_nlp_pipeline()
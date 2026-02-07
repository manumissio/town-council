import sys
import os
import time
import spacy
from sqlalchemy.orm import sessionmaker

# Add project root to path for consistent imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from pipeline.models import Catalog, db_connect, create_tables
from pipeline.utils import is_likely_human_name

# Global cache for the NLP model to avoid reloading in the same process
_cached_nlp = None

def get_municipal_nlp_model():
    """
    Creates an NLP model customized for municipal documents.
    Adds a 'RuleRuler' with deterministic patterns.
    """
    global _cached_nlp
    if _cached_nlp:
        return _cached_nlp
        
    # Load the base English model.
    try:
        nlp = spacy.load("en_core_web_sm", disable=["parser", "lemmatizer"])
    except OSError:
        # Fallback if model not found
        import en_core_web_sm
        nlp = en_core_web_sm.load(disable=["parser", "lemmatizer"])
    
    # Create the EntityRuler. 
    ruler = nlp.add_pipe("entity_ruler", before="ner")
    
    patterns = [
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
        {"label": "PERSON", "pattern": [{"LOWER": "moved"}, {"LOWER": "by"}, {"IS_TITLE": True}]},
        {"label": "PERSON", "pattern": [{"LOWER": "moved"}, {"LOWER": "by"}, {"IS_TITLE": True}, {"IS_TITLE": True}]},
        {"label": "PERSON", "pattern": [{"LOWER": "seconded"}, {"LOWER": "by"}, {"IS_TITLE": True}]},
        {"label": "PERSON", "pattern": [{"LOWER": "seconded"}, {"LOWER": "by"}, {"IS_TITLE": True}, {"IS_TITLE": True}]},
        {"label": "PERSON", "pattern": [{"LOWER": "ayes"}, {"ORTH": ":"}, {"IS_TITLE": True}]},
        {"label": "PERSON", "pattern": [{"LOWER": "noes"}, {"ORTH": ":"}, {"IS_TITLE": True}]},
    ]
    
    ruler.add_patterns(patterns)
    _cached_nlp = nlp
    return nlp

def extract_entities(text):
    """
    Extracts entities from a single text string.
    Used by parallel_processor.
    """
    if not text:
        return None
        
    nlp = get_municipal_nlp_model()
    # Process only first 100k chars to prevent memory issues
    doc = nlp(text[:100000])
    
    entities = {
        "orgs": [],
        "locs": [],
        "persons": []
    }

    for ent in doc.ents:
        name = ent.text.strip().replace('\n', ' ')
        
        triggers = ["moved by", "seconded by", "mayor", "councilmember", "commissioner", "chair", "director", "ayes :", "noes :"]
        for trigger in triggers:
            if name.lower().startswith(trigger):
                name = name[len(trigger):].strip()
        
        if len(name) < 2 or len(name) > 100:
            continue

        if ent.label_ == "PERSON":
            if not is_likely_human_name(name):
                continue
            if name not in entities["persons"]:
                entities["persons"].append(name)
        
        elif ent.label_ == "ORG" and name not in entities["orgs"]:
            entities["orgs"].append(name)
        
        elif ent.label_ in ["GPE", "LOC"] and name not in entities["locs"]:
            entities["locs"].append(name)
            
    return entities

def run_nlp_pipeline():
    """
    Legacy batch processing function.
    """
    print("Loading Customized Municipal NLP model...")
    nlp = get_municipal_nlp_model()

    engine = db_connect()
    create_tables(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    to_process = session.query(Catalog).filter(
        Catalog.content != None,
        Catalog.content != "",
        Catalog.entities == None
    ).all()

    print(f"Found {len(to_process)} documents for NLP processing.")

    for record in to_process:
        record.entities = extract_entities(record.content)
        print(f"Processed {record.filename}")

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
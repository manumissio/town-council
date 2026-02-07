import sys
import os
import time
import spacy
from sqlalchemy.orm import sessionmaker

# Add project root to path for consistent imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from pipeline.models import Catalog, db_connect, create_tables
from pipeline.utils import is_likely_human_name

from spacy.language import Language

# Global cache for the NLP model to avoid reloading in the same process
_cached_nlp = None

@Language.component("scrub_municipal_noise")
def scrub_municipal_noise(doc):
    """
    POST-NER VALIDATION:
    We look at every 'PERSON' found by the AI and apply common-sense rules.
    """
    new_ents = []
    # Known titles that we trust even if the name is just one word (e.g. 'Mayor Arreguin')
    trust_titles = ['mayor', 'councilmember', 'commissioner', 'chair', 'director', 'ayes', 'noes']
    
    for ent in doc.ents:
        if ent.label_ == "PERSON":
            text = ent.text.strip().lower()
            
            # RULE 1: If it starts with a trusted title, we KEEP it regardless of spaces.
            # This handles 'Mayor Arreguin' or 'Ayes: Harrison' correctly.
            is_trusted = any(text.startswith(t) for t in trust_titles)
            
            if not is_trusted:
                # If NOT trusted, apply strict human-name checks:
                
                # RULE 2: Proper Noun Check. 
                # Legitimate names should contain at least one Proper Noun (PROPN).
                # This filters out generic roles like 'Local Artist' (ADJ NOUN).
                if not any(token.pos_ == "PROPN" for token in ent):
                    continue

                # Names usually have a space (First Last).
                if ' ' not in text:
                    continue
                    
                # Names don't contain digits.
                if any(char.isdigit() for char in text):
                    continue
                
                # Non-human root words.
                root_lemma = ent.root.lemma_.lower()
                if root_lemma in ['ordinance', 'resolution', 'item', 'page', 'exhibit', 'section', 'table', 'bid']:
                    continue
        
        new_ents.append(ent)
    
    doc.ents = new_ents
    return doc

def get_municipal_nlp_model():
    """
    Creates an NLP model customized for municipal documents.
    1. Pre-NER EntityRuler to block boilerplate.
    2. Statistical NER for name discovery.
    3. Post-NER 'scrub_municipal_noise' component for common-sense cleanup.
    """
    global _cached_nlp
    if _cached_nlp:
        return _cached_nlp
        
    # Load the base English model. We need parser and lemmatizer for our 'Scrubbing' logic.
    try:
        nlp = spacy.load("en_core_web_sm")
    except OSError:
        import en_core_web_sm
        nlp = en_core_web_sm.load()
    
    # --------------------------------------------------------------------------
    # STEP 1: Pre-NER Boilerplate Exclusion
    # We tag common noise as 'BOILERPLATE' before the AI starts.
    # --------------------------------------------------------------------------
    ruler = nlp.add_pipe("entity_ruler", before="ner")
    
    # PROBLEM: Job titles and section headers are often mistaken for people.
    # SOLUTION: Explicitly label them so the AI ignores them.
    patterns = [
        # Explicit Boilerplate
        {"label": "BOILERPLATE", "pattern": [{"LOWER": "item"}, {"IS_DIGIT": True}]},
        {"label": "BOILERPLATE", "pattern": [{"LOWER": "page"}, {"IS_DIGIT": True}]},
        {"label": "BOILERPLATE", "pattern": [{"LOWER": "exhibit"}, {"IS_ALPHA": True, "LENGTH": 1}]},
        {"label": "BOILERPLATE", "pattern": [{"LOWER": "city"}, {"LOWER": "clerk"}]},
        {"label": "BOILERPLATE", "pattern": [{"LOWER": "city"}, {"LOWER": "manager"}]},
        {"label": "BOILERPLATE", "pattern": [{"LOWER": "deputy"}, {"LOWER": "director"}]},
        {"label": "BOILERPLATE", "pattern": [{"LOWER": "roll"}, {"LOWER": "call"}]},
        {"label": "BOILERPLATE", "pattern": [{"LOWER": "annotated"}, {"LOWER": "agenda"}]},
        
        # Title-based Person Triggers (Positive Bias)
        # We catch 'Mayor [Name]' or 'Councilmember [Name]' explicitly.
        {"label": "PERSON", "pattern": [{"LOWER": "mayor"}, {"IS_TITLE": True}, {"IS_TITLE": True}]},
        {"label": "PERSON", "pattern": [{"LOWER": "councilmember"}, {"IS_TITLE": True}, {"IS_TITLE": True}]},
        {"label": "PERSON", "pattern": [{"LOWER": "vice"}, {"LOWER": "mayor"}, {"IS_TITLE": True}, {"IS_TITLE": True}]},
        {"label": "PERSON", "pattern": [{"LOWER": "moved"}, {"LOWER": "by"}, {"IS_TITLE": True}, {"IS_TITLE": True}]},
        {"label": "PERSON", "pattern": [{"LOWER": "seconded"}, {"LOWER": "by"}, {"IS_TITLE": True}, {"IS_TITLE": True}]},
        {"label": "PERSON", "pattern": [{"LOWER": "ayes"}, {"ORTH": ":"}, {"IS_TITLE": True}]},
        {"label": "PERSON", "pattern": [{"LOWER": "noes"}, {"ORTH": ":"}, {"IS_TITLE": True}]},
    ]
    
    ruler.add_patterns(patterns)
    
    # --------------------------------------------------------------------------
    # STEP 2: Post-NER Common-Sense Scrubbing
    # --------------------------------------------------------------------------
    nlp.add_pipe("scrub_municipal_noise", last=True)

    _cached_nlp = nlp
    return nlp

def extract_entities(text):
    """
    Extracts entities from a single text string.
    """
    if not text:
        return None
        
    nlp = get_municipal_nlp_model()
    doc = nlp(text[:100000])
    
    entities = {
        "orgs": [],
        "locs": [],
        "persons": []
    }

    for ent in doc.ents:
        # Ignore our custom BOILERPLATE label in the final results
        if ent.label_ == "BOILERPLATE":
            continue

        name = ent.text.strip().replace('\n', ' ')
        
        # Clean up titles from names (e.g. 'Mayor Jesse Arreguin' -> 'Jesse Arreguin')
        prefixes = ["moved by", "seconded by", "mayor", "councilmember", "vice mayor", "chair", "director"]
        for prefix in prefixes:
            if name.lower().startswith(prefix):
                name = name[len(prefix):].strip()
        
        if len(name) < 2 or len(name) > 100:
            continue

        if ent.label_ == "PERSON":
            # SECURITY: Final check against the expanded blacklist
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
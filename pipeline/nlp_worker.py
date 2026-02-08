import sys
import os
import time
import spacy
import threading

# Add project root to path for consistent imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from pipeline.models import Catalog
from pipeline.db_session import db_session
from pipeline.utils import is_likely_human_name
from pipeline.config import NLP_MAX_TEXT_LENGTH

from spacy.language import Language

# Global cache for the NLP model to avoid reloading in the same process
# Why cache? Loading SpaCy's NLP model takes ~2 seconds and uses ~500MB RAM
# By caching it, we only pay this cost once per process
_cached_nlp = None
_model_lock = threading.Lock()  # Prevents multiple threads from loading simultaneously

@Language.component("scrub_municipal_noise")
def scrub_municipal_noise(doc):
    """
    POST-NER VALIDATION:
    We look at every 'PERSON' found by the AI and apply common-sense rules.
    """
    new_ents = []
    # Known titles that we trust
    trust_titles = [
        'mayor', 'councilmember', 'commissioner', 'chair', 'director', 
        'ayes', 'noes', 'moved', 'seconded', 'vice mayor'
    ]
    
    for ent in doc.ents:
        if ent.label_ == "PERSON":
            text = ent.text.strip()
            text_lower = text.lower()
            
            # RULE 1: Trusted Title Exception
            # If it starts with a trusted title, we allow it to bypass some checks.
            is_trusted = any(text_lower.startswith(t) for t in trust_titles)
            
            # RULE 2: Character & Blacklist Guardrail
            # We use the centralized bouncer. 
            # We allow single words if trusted (e.g. 'Ayes: Harrison').
            if not is_likely_human_name(text, allow_single_word=is_trusted):
                continue

            # RULE 3: Proper Noun Check. 
            # Legitimate names should contain at least one Proper Noun (PROPN).
            # This filters out generic roles like 'Local Artist'.
            if not any(token.pos_ == "PROPN" for token in ent):
                continue
        
        new_ents.append(ent)
    
    doc.ents = new_ents
    return doc

def get_municipal_nlp_model():
    """
    Creates an NLP model customized for municipal documents.

    What's NLP? Natural Language Processing - teaching computers to understand human language.
    What's NER? Named Entity Recognition - finding people, places, organizations in text.

    Our pipeline (3 layers of filtering):
    1. Pre-NER EntityRuler: Block obvious boilerplate ("Item 1", "City Clerk")
    2. Statistical NER: AI model identifies potential person names
    3. Post-NER Scrubbing: Common-sense rules filter out noise

    Why 3 layers? Municipal documents are full of noise that confuses standard NLP models.
    Without these filters, "City Staff" and "Item 5" would be tagged as people.
    """
    global _cached_nlp

    # Fast path: if model already loaded, return it immediately
    if _cached_nlp:
        return _cached_nlp

    # Thread-safe model loading
    # Only one thread should load the model at a time
    with _model_lock:
        # Double-check after acquiring lock (another thread might have loaded it)
        if _cached_nlp:
            return _cached_nlp

        # Load the base English model (includes parser, NER, lemmatizer)
        # This model is ~13MB and takes ~2 seconds to load
        try:
            nlp = spacy.load("en_core_web_sm")
        except OSError:
            # Fallback: try direct import if load() fails
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
        # Both single-word and double-word names are supported.
        {"label": "PERSON", "pattern": [{"LOWER": "mayor"}, {"IS_TITLE": True}]},
        {"label": "PERSON", "pattern": [{"LOWER": "mayor"}, {"IS_TITLE": True}, {"IS_TITLE": True}]},
        {"label": "PERSON", "pattern": [{"LOWER": "councilmember"}, {"IS_TITLE": True}]},
        {"label": "PERSON", "pattern": [{"LOWER": "councilmember"}, {"IS_TITLE": True}, {"IS_TITLE": True}]},
        {"label": "PERSON", "pattern": [{"LOWER": "vice"}, {"LOWER": "mayor"}, {"IS_TITLE": True}]},
        {"label": "PERSON", "pattern": [{"LOWER": "vice"}, {"LOWER": "mayor"}, {"IS_TITLE": True}, {"IS_TITLE": True}]},
        {"label": "PERSON", "pattern": [{"LOWER": "moved"}, {"LOWER": "by"}, {"IS_TITLE": True}]},
        {"label": "PERSON", "pattern": [{"LOWER": "moved"}, {"LOWER": "by"}, {"IS_TITLE": True}, {"IS_TITLE": True}]},
        {"label": "PERSON", "pattern": [{"LOWER": "seconded"}, {"LOWER": "by"}, {"IS_TITLE": True}]},
        {"label": "PERSON", "pattern": [{"LOWER": "seconded"}, {"LOWER": "by"}, {"IS_TITLE": True}, {"IS_TITLE": True}]},
        {"label": "PERSON", "pattern": [{"LOWER": "ayes"}, {"ORTH": ":"}, {"IS_TITLE": True}]},
        {"label": "PERSON", "pattern": [{"LOWER": "noes"}, {"ORTH": ":"}, {"IS_TITLE": True}]},
    ]
    
    ruler.add_patterns(patterns)
    
        # --------------------------------------------------------------------------
        # STEP 2: Post-NER Common-Sense Scrubbing
        # This custom component filters out noise that made it through the AI
        # --------------------------------------------------------------------------
        nlp.add_pipe("scrub_municipal_noise", last=True)

        # Cache the fully configured model for reuse
        _cached_nlp = nlp
        return nlp

def extract_entities(text):
    """
    Extracts entities from a single text string.

    What gets extracted:
    - persons: People's names (after extensive filtering)
    - orgs: Organizations mentioned
    - locs: Geographic locations

    Why truncate text?
    SpaCy's NER model can handle ~100K characters before memory becomes an issue.
    Most meeting documents have key entities in the first portion anyway.
    """
    if not text:
        return None

    nlp = get_municipal_nlp_model()

    # Process text (truncate to prevent memory issues with very large documents)
    doc = nlp(text[:NLP_MAX_TEXT_LENGTH])
    
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
        prefixes = ["moved by", "seconded by", "mayor", "councilmember", "vice mayor", "chair", "director", "ayes :", "noes :"]
        has_prefix = False
        for prefix in prefixes:
            if name.lower().startswith(prefix):
                name = name[len(prefix):].strip()
                has_prefix = True
        
        if len(name) < 2 or len(name) > 100:
            continue

        if ent.label_ == "PERSON":
            # SECURITY: Final check against the expanded blacklist
            # If we stripped a title, we allow single-word names (e.g. 'Mayor Arreguin')
            if not is_likely_human_name(name, allow_single_word=has_prefix):
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

    What this does:
    1. Loads the customized NLP model (with municipal document filters)
    2. Finds all documents that need entity extraction
    3. Extracts persons, organizations, and locations from each document
    4. Saves the results to the database

    This is called "legacy" because it processes all documents at once.
    Modern usage: Call extract_entities() directly for individual documents.
    """
    print("Loading Customized Municipal NLP model...")
    nlp = get_municipal_nlp_model()

    # Use context manager for automatic session cleanup and error handling
    # Why? The context manager automatically rolls back on errors and closes the session
    with db_session() as session:
        # Find all documents that have content but haven't been processed for entities yet
        to_process = session.query(Catalog).filter(
            Catalog.content != None,
            Catalog.content != "",
            Catalog.entities == None
        ).all()

        print(f"Found {len(to_process)} documents for NLP processing.")

        # Process each document: extract names, places, organizations
        for record in to_process:
            record.entities = extract_entities(record.content)
            print(f"Processed {record.filename}")

        # Save all changes to the database at once
        # If this fails, the context manager will automatically rollback
        session.commit()
        print("NLP processing complete.")

if __name__ == "__main__":
    run_nlp_pipeline()
import time
import spacy
from sqlalchemy.orm import sessionmaker
from models import Catalog, db_connect, create_tables

def run_nlp_pipeline():
    """
    Scans meeting minutes to automatically identify important names.
    
    How it works (Named Entity Recognition):
    1. It loads a pre-trained language model (SpaCy).
    2. It reads documents that haven't been analyzed yet.
    3. It finds and categorizes names of Organizations (ORG) and Locations (GPE/LOC).
    4. It saves these lists to the database so they can be used for search filters.
    """
    print("Loading SpaCy NLP model (en_core_web_sm)...")
    try:
        # Load the English language model.
        # We disable 'parser' and 'lemmatizer' because we only need Entity Recognition (NER),
        # and disabling the others makes it run much faster.
        nlp = spacy.load("en_core_web_sm", disable=["parser", "lemmatizer"])
    except OSError:
        print("Error: SpaCy model 'en_core_web_sm' not found. Ensure it is installed.")
        return

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
    # We limit text to the first 100k characters to prevent running out of memory on huge PDFs.
    doc_tuples = [(record, record.content[:100000]) for record in to_process]
    
    # nlp.pipe processes multiple texts in parallel, which is much faster than a loop.
    for record, spacy_doc in zip([r for r, t in doc_tuples], 
                                 nlp.pipe([t for r, t in doc_tuples], batch_size=20)):
        
        entities = {
            "orgs": [],
            "locs": [],
            "persons": []
        }

        # Loop through all the "entities" (names/places) the model found.
        for ent in spacy_doc.ents:
            # Clean up the text (remove extra spaces or newlines).
            text = ent.text.strip().replace('\n', ' ')
            
            # Skip very short or very long garbage results.
            if len(text) < 2 or len(text) > 100:
                continue

            # Categorize the entity.
            # ORG = Companies, Agencies, Institutions (e.g., "Police Department", "PG&E")
            if ent.label_ == "ORG" and text not in entities["orgs"]:
                entities["orgs"].append(text)
            # GPE/LOC = Countries, Cities, States (e.g., "Belmont", "California")
            elif ent.label_ in ["GPE", "LOC"] and text not in entities["locs"]:
                entities["locs"].append(text)
            # PERSON = People's names (e.g., "Mayor Smith")
            elif ent.label_ == "PERSON" and text not in entities["persons"]:
                entities["persons"].append(text)

        # Save the results as a JSON object in the database.
        record.entities = entities
        print(f"Processed {record.filename}: Found {len(entities['orgs'])} Orgs, {len(entities['locs'])} Locs")

    # Save all changes to the database.
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
import os
import time
import json
from google import genai
from sqlalchemy.orm import sessionmaker
from models import Catalog, AgendaItem, Document, db_connect, create_tables
from utils import generate_ocd_id

def segment_agendas():
    """
    Intelligence Worker: Uses Gemini 2.0 AI to split large OCR documents 
    into individual, searchable 'Agenda Items'.
    
    Why this is needed:
    Users often search for a specific topic (e.g., 'Biking'). Instead of 
    sending them to a 100-page PDF, this worker allows the system to take 
    them directly to the exact 'Agenda Item' where biking was discussed.
    """
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        print("Error: GEMINI_API_KEY not set. Skipping agenda segmentation.")
        return

    client = genai.Client(api_key=api_key)
    
    engine = db_connect()
    create_tables(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Find documents that have text content but no segmented agenda items yet.
    # We join with 'Document' to ensure we only process records linked to a 'Meeting' (Event).
    to_process = session.query(Catalog).join(
        Document, Catalog.id == Document.catalog_id
    ).outerjoin(
        AgendaItem, Catalog.id == AgendaItem.catalog_id
    ).filter(
        Catalog.content != None,
        Catalog.content != "",
        AgendaItem.id == None # Only process if it has no items yet
    ).all()

    print(f"Found {len(to_process)} documents to segment into agenda items.")

    for catalog in to_process:
        # Get the associated Event (Meeting) so we can link the items correctly.
        # Note: A Catalog entry can be linked to multiple Documents (e.g., same PDF in different cities),
        # but usually it's 1:1. We pick the first associated event.
        doc = session.query(Document).filter_by(catalog_id=catalog.id).first()
        if not doc or not doc.event_id:
            continue

        print(f"Segmenting: {catalog.filename}...")
        
        try:
            prompt = (
                "You are an expert civic data analyst. Your task is to extract individual agenda items "
                "from the following town council meeting minutes. "
                "For each distinct agenda item or discussion topic, extract: "
                "1. Title: The short name of the item (e.g., 'Zoning Change for Main St'). "
                "2. Description: A 1-2 sentence summary of the discussion. "
                "3. Classification: One of [Action, Discussion, Consent, Public Hearing, Presentation]. "
                "4. Result: If a vote happened, what was the outcome? (e.g., 'Passed', 'Failed'). \n"
                "Leave empty if no result is clear.\n\n"
                "Return the data ONLY as a valid JSON array of objects with the keys: \n"
                "'order', 'title', 'description', 'classification', 'result'. \n"
                "Be extremely precise and do not include any text before or after the JSON.\n\n"
                f"TEXT: {catalog.content[:150000]}"
            )

            # Using 'gemini-2.0-flash' for efficient extraction.
            # We use a deterministic config (temperature 0.0).
            response = client.models.generate_content(
                model='gemini-2.0-flash',
                contents=prompt,
                config={
                    "temperature": 0.0,
                    "response_mime_type": "application/json"
                }
            )
            
            if response and response.text:
                items_data = json.loads(response.text)
                
                # Create the structured AgendaItem records in the database.
                for data in items_data:
                    item = AgendaItem(
                        ocd_id=generate_ocd_id('agendaitem'),
                        event_id=doc.event_id,
                        catalog_id=catalog.id,
                        order=data.get('order'),
                        title=data.get('title', 'Untitled Item'),
                        description=data.get('description'),
                        classification=data.get('classification'),
                        result=data.get('result')
                    )
                    session.add(item)
                
                session.commit()
                print(f"Successfully extracted {len(items_data)} agenda items.")
            else:
                print("Gemini returned empty response.")

            # Respect rate limits
            time.sleep(3)

        except Exception as e:
            print(f"Error segmenting {catalog.filename}: {e}")
            session.rollback()

    session.close()
    print("Agenda segmentation process complete.")

if __name__ == "__main__":
    segment_agendas()

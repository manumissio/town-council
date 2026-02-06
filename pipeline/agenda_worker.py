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
    # CAP: Only process 10 documents per run to avoid 429 errors on free tiers.
    to_process = session.query(Catalog).join(
        Document, Catalog.id == Document.catalog_id
    ).outerjoin(
        AgendaItem, Catalog.id == AgendaItem.catalog_id
    ).filter(
        Catalog.content != None,
        Catalog.content != "",
        AgendaItem.id == None
    ).limit(10).all()

    print(f"Found {len(to_process)} documents to segment (Processing batch of 10)...")
    
    # Safety: Wait 10s before starting to ensure a fresh Rate Limit bucket
    if to_process:
        print("Waiting 10s for API warm-up...")
        time.sleep(10)

    for catalog in to_process:
        doc = session.query(Document).filter_by(catalog_id=catalog.id).first()
        if not doc or not doc.event_id:
            continue

        print(f"Segmenting: {catalog.filename}...")
        
        # Retry logic for Rate Limits (429)
        max_retries = 3
        retry_delay = 20
        
        for attempt in range(max_retries):
            try:
                # TOKEN OPTIMIZATION: Reduced to 50k chars to stay under TPM (Tokens Per Minute) limits.
                # Most agendas have their meat in the first 20-30 pages.
                text_snippet = (catalog.content or "")[:50000]

                prompt = (
                    "Extract individual agenda items from these city meeting minutes. "
                    "For each item, provide: order, title, description (1 sentence), classification, and result. "
                    "Return ONLY a JSON array. \n\n"
                    f"TEXT: {text_snippet}"
                )

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
                    break
                else:
                    print("Gemini returned empty response.")
                    break

            except Exception as e:
                if "429" in str(e) or "Resource exhausted" in str(e):
                    print(f"Rate limit hit. Retrying in {retry_delay}s... (Attempt {attempt+1}/{max_retries})")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    print(f"Error segmenting {catalog.filename}: {e}")
                    session.rollback()
                    break

        # Respect RPM (Requests Per Minute) limits
        time.sleep(10)

    session.close()
    print("Agenda segmentation batch complete.")

if __name__ == "__main__":
    segment_agendas()
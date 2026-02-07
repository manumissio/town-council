import os
import time
import json
from sqlalchemy.orm import sessionmaker
from models import Catalog, AgendaItem, Document, db_connect, create_tables
from utils import generate_ocd_id
from llm import LocalAI

def segment_agendas():
    """
    Intelligence Worker: Uses Local AI (Gemma 3) to split large OCR documents 
    into individual, searchable 'Agenda Items'.
    
    Why this is needed:
    Users often search for a specific topic (e.g., 'Biking'). Instead of 
    sending them to a 100-page PDF, this worker allows the system to take 
    them directly to the exact 'Agenda Item' where biking was discussed.
    """
    # Initialize the local brain (Singleton)
    local_ai = LocalAI()
    
    engine = db_connect()
    create_tables(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Find documents that have text content but no segmented agenda items yet.
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

    for catalog in to_process:
        doc = session.query(Document).filter_by(catalog_id=catalog.id).first()
        if not doc or not doc.event_id:
            continue

        print(f"Segmenting: {catalog.filename}...")
        
        try:
            # Call the local brain to extract the agenda
            items_data = local_ai.extract_agenda(catalog.content)
            
            if items_data:
                for data in items_data:
                    # Validate: Ensure at least a title exists
                    if not data.get('title'):
                        continue
                        
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
                print("AI returned no items.")

        except Exception as e:
            print(f"Error segmenting {catalog.filename}: {e}")
            session.rollback()

    session.close()
    print("Agenda segmentation batch complete.")

if __name__ == "__main__":
    segment_agendas()
import os
import time
import json
from sqlalchemy.orm import sessionmaker
from pipeline.models import Catalog, AgendaItem, Document, db_connect, create_tables
from pipeline.utils import generate_ocd_id
from pipeline.llm import LocalAI

def segment_document_agenda(catalog_id):
    """
    Intelligence Worker: Uses Local AI (Gemma 3) to split a single document
    into individual, searchable 'Agenda Items'.
    """
    local_ai = LocalAI()
    
    engine = db_connect()
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        catalog = session.get(Catalog, catalog_id)
        if not catalog or not catalog.content:
            return

        doc = session.query(Document).filter_by(catalog_id=catalog.id).first()
        if not doc or not doc.event_id:
            return

        # Call the local brain to extract the agenda
        items_data = local_ai.extract_agenda(catalog.content)
        
        if items_data:
            # Clear old items to prevent duplicates
            session.query(AgendaItem).filter_by(catalog_id=catalog.id).delete()
            
            for data in items_data:
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
    except Exception as e:
        print(f"Error segmenting {catalog_id}: {e}")
        session.rollback()
    finally:
        session.close()

def segment_agendas():
    """
    Legacy batch processing function.
    """
    engine = db_connect()
    Session = sessionmaker(bind=engine)
    session = Session()

    to_process = session.query(Catalog).join(
        Document, Catalog.id == Document.catalog_id
    ).outerjoin(
        AgendaItem, Catalog.id == AgendaItem.catalog_id
    ).filter(
        Catalog.content != None,
        Catalog.content != "",
        AgendaItem.id == None
    ).limit(10).all()

    ids = [c.id for c in to_process]
    session.close()

    for cid in ids:
        segment_document_agenda(cid)

if __name__ == "__main__":
    segment_agendas()
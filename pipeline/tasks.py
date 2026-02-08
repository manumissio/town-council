from celery import Celery
import os
import logging
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError

from pipeline.models import db_connect, Catalog, Document, AgendaItem
from pipeline.llm import LocalAI
from pipeline.utils import generate_ocd_id

# Setup logging
logger = logging.getLogger("celery-worker")

# Celery broker queues tasks; result backend stores task results.
app = Celery('tasks')

# Read connection settings from environment.
app.conf.broker_url = os.getenv('CELERY_BROKER_URL', 'redis://redis:6379/0')
app.conf.result_backend = os.getenv('CELERY_RESULT_BACKEND', 'redis://redis:6379/0')

# Database Setup
engine = db_connect()
SessionLocal = sessionmaker(bind=engine)

@app.task(bind=True, max_retries=3)
def generate_summary_task(self, catalog_id: int):
    """
    Background task: generate and store a catalog summary.
    """
    db = SessionLocal()
    local_ai = LocalAI()
    
    try:
        logger.info(f"Starting summarization for Catalog ID {catalog_id}")
        catalog = db.get(Catalog, catalog_id)
        
        if not catalog or not catalog.content:
            return {"error": "No content to summarize"}
        
        # Return cached value when already summarized.
        if catalog.summary:
            return {"status": "cached", "summary": catalog.summary}
            
        summary = local_ai.summarize(catalog.content)
        
        # Retry instead of storing an empty summary.
        if summary is None:
            raise RuntimeError("AI Summarization returned None (Model missing or error)")
        
        # Update DB
        catalog.summary = summary
        db.commit()
        
        logger.info(f"Summarization complete for Catalog ID {catalog_id}")
        return {"status": "complete", "summary": summary}

    except (SQLAlchemyError, RuntimeError, ValueError) as e:
        logger.error(f"Task failed: {e}")
        db.rollback()
        raise self.retry(exc=e, countdown=60)
    finally:
        db.close()

@app.task(bind=True, max_retries=3)
def segment_agenda_task(self, catalog_id: int):
    """
    Background task: segment catalog text into agenda items.
    """
    db = SessionLocal()
    local_ai = LocalAI()
    
    try:
        logger.info(f"Starting segmentation for Catalog ID {catalog_id}")
        catalog = db.get(Catalog, catalog_id)
        
        if not catalog or not catalog.content:
            return {"error": "No content"}
            
        doc = db.query(Document).filter_by(catalog_id=catalog_id).first()
        if not doc:
            return {"error": "Document not linked to event"}
            
        items_data = local_ai.extract_agenda(catalog.content)
        
        count = 0
        items_to_return = []
        if items_data:
            # Clear old items so re-runs remain idempotent.
            db.query(AgendaItem).filter_by(catalog_id=catalog_id).delete()
            
            for data in items_data:
                if not data.get('title'): continue
                
                item = AgendaItem(
                    ocd_id=generate_ocd_id('agendaitem'),
                    event_id=doc.event_id,
                    catalog_id=catalog_id,
                    order=data.get('order'),
                    title=data.get('title', 'Untitled'),
                    description=data.get('description'),
                    classification=data.get('classification'),
                    result=data.get('result')
                )
                db.add(item)
                items_to_return.append({
                    "title": item.title,
                    "description": item.description,
                    "order": item.order,
                    "classification": item.classification,
                    "result": item.result
                })
                count += 1
            
            db.commit()
            
        logger.info(f"Segmentation complete: {count} items found")
        return {"status": "complete", "item_count": count, "items": items_to_return}

    except (SQLAlchemyError, RuntimeError, KeyError, ValueError) as e:
        logger.error(f"Task failed: {e}")
        db.rollback()
        raise self.retry(exc=e, countdown=60)
    finally:
        db.close()

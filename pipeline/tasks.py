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

# Initialize Celery
# The broker is where tasks are queued (Redis)
# The backend is where results are stored (Redis)
app = Celery('tasks')

# SECURITY: Always get Redis connection from environment variables
# Never hardcode passwords in source code - they end up in version control!
# If these env vars aren't set, the app will fail loudly (which is better than using a default password)
app.conf.broker_url = os.getenv('CELERY_BROKER_URL', 'redis://redis:6379/0')
app.conf.result_backend = os.getenv('CELERY_RESULT_BACKEND', 'redis://redis:6379/0')

# Database Setup
engine = db_connect()
SessionLocal = sessionmaker(bind=engine)

@app.task(bind=True, max_retries=3)
def generate_summary_task(self, catalog_id: int):
    """
    Background Task: Generate AI Summary
    
    Why this is async:
    Generating a summary takes ~5-10 seconds on a CPU.
    By doing this in the background, the API returns instantly.
    """
    db = SessionLocal()
    local_ai = LocalAI()
    
    try:
        logger.info(f"Starting summarization for Catalog ID {catalog_id}")
        catalog = db.get(Catalog, catalog_id)
        
        if not catalog or not catalog.content:
            return {"error": "No content to summarize"}
        
        # Check if already done (Idempotency)
        if catalog.summary:
            return {"status": "cached", "summary": catalog.summary}
            
        # Heavy Lifting (CPU Bound)
        summary = local_ai.summarize(catalog.content)
        
        # SAFETY CHECK:
        # If the AI didn't run (because the model is missing or crashed), it returns None.
        # We MUST NOT save this to the database. If we saved "Error", the system
        # would think it finished the job and never try again.
        if summary is None:
            raise RuntimeError("AI Summarization returned None (Model missing or error)")
        
        # Update DB
        catalog.summary = summary
        db.commit()
        
        logger.info(f"Summarization complete for Catalog ID {catalog_id}")
        return {"status": "complete", "summary": summary}

    except (SQLAlchemyError, RuntimeError, ValueError) as e:
        # Celery task errors: What can fail in async summarization tasks?
        # - SQLAlchemyError: Database connection lost, commit failed
        # - RuntimeError: AI model failed to generate summary (see llm.py)
        # - ValueError: Invalid catalog_id or malformed content
        # Why catch in Celery tasks? Tasks run asynchronously - errors shouldn't crash worker
        # Celery will retry the task in 60 seconds (3 attempts total)
        logger.error(f"Task failed: {e}")
        db.rollback()
        # Retry in 60 seconds if it failed
        raise self.retry(exc=e, countdown=60)
    finally:
        db.close()

@app.task(bind=True, max_retries=3)
def segment_agenda_task(self, catalog_id: int):
    """
    Background Task: Segment Agenda Items
    """
    db = SessionLocal()
    local_ai = LocalAI()
    
    try:
        logger.info(f"Starting segmentation for Catalog ID {catalog_id}")
        catalog = db.get(Catalog, catalog_id)
        
        if not catalog or not catalog.content:
            return {"error": "No content"}
            
        # Get link to event
        doc = db.query(Document).filter_by(catalog_id=catalog_id).first()
        if not doc:
            return {"error": "Document not linked to event"}
            
        # Heavy Lifting
        items_data = local_ai.extract_agenda(catalog.content)
        
        count = 0
        items_to_return = []
        if items_data:
            # Clear old items to prevent duplicates if re-run
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
        # Agenda segmentation task errors: What can fail during async AI extraction?
        # - SQLAlchemyError: Database error saving agenda items
        # - RuntimeError: AI model failed during agenda extraction
        # - KeyError: Missing expected fields in AI response
        # - ValueError: Invalid catalog_id or unparseable content
        # Same retry logic as summarization task
        logger.error(f"Task failed: {e}")
        db.rollback()
        raise self.retry(exc=e, countdown=60)
    finally:
        db.close()

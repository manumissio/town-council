from celery import Celery
import os
import logging
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError

from pipeline.models import db_connect, Catalog, Document
from pipeline.llm import LocalAI
from pipeline.agenda_service import persist_agenda_items
from pipeline.agenda_resolver import resolve_agenda_items
from pipeline.models import AgendaItem

# Register worker metrics (safe in non-worker contexts; the HTTP server only starts
# when TC_WORKER_METRICS_PORT is set and the Celery worker is ready).
from pipeline import metrics as _worker_metrics  # noqa: F401

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
def generate_summary_task(self, catalog_id: int, force: bool = False):
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

        # Decide how to summarize based on the *document type*.
        # Many cities publish agenda PDFs without corresponding minutes PDFs.
        # If we summarize an agenda using a "minutes" prompt, the output looks incorrect.
        doc = db.query(Document).filter_by(catalog_id=catalog_id).first()
        doc_kind = (doc.category or "unknown") if doc else "unknown"
        
        # Return cached value when already summarized, unless the caller forces a refresh.
        #
        # Why have `force`?
        # Summaries are cached on the Catalog row. When we improve the prompt/cleanup logic,
        # old low-quality summaries won't change unless we regenerate them.
        if (not force) and catalog.summary:
            return {"status": "cached", "summary": catalog.summary}

        # If agenda items already exist, prefer a deterministic agenda-style summary instead
        # of relying entirely on the LLM. This is fast, stable, and avoids "how to attend"
        # boilerplate dominating the output.
        #
        # This is intentionally simple: we list the first few agenda item titles in order.
        if doc_kind == "agenda":
            existing_items = (
                db.query(AgendaItem)
                .filter_by(catalog_id=catalog_id)
                .order_by(AgendaItem.order)
                .limit(6)
                .all()
            )
            if existing_items:
                titles = [it.title.strip() for it in existing_items if it.title and it.title.strip()]
                titles = titles[:3]
                if titles:
                    summary = "\n".join(f"* {t}" for t in titles)
                else:
                    summary = local_ai.summarize(catalog.content, doc_kind=doc_kind)
            else:
                summary = local_ai.summarize(catalog.content, doc_kind=doc_kind)
        else:
            summary = local_ai.summarize(catalog.content, doc_kind=doc_kind)
        
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
            
        resolved = resolve_agenda_items(db, catalog, doc, local_ai)
        items_data = resolved["items"]
        
        count = 0
        items_to_return = []
        if items_data:
            created_items = persist_agenda_items(db, catalog_id, doc.event_id, items_data)
            for item in created_items:
                items_to_return.append({
                    "title": item.title,
                    "description": item.description,
                    "order": item.order,
                    "classification": item.classification,
                    "result": item.result,
                    "page_number": item.page_number,
                    "source": resolved["source_used"],
                })
                count += 1
            
            db.commit()
            
        logger.info(f"Segmentation complete: {count} items found (source={resolved['source_used']})")
        return {
            "status": "complete",
            "item_count": count,
            "items": items_to_return,
            "source_used": resolved["source_used"],
            "quality_score": resolved["quality_score"],
        }

    except (SQLAlchemyError, RuntimeError, KeyError, ValueError) as e:
        logger.error(f"Task failed: {e}")
        db.rollback()
        raise self.retry(exc=e, countdown=60)
    finally:
        db.close()

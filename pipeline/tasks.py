from celery import Celery
from celery.signals import worker_ready
import os
import logging
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError

from pipeline.models import db_connect, Catalog, Document
from pipeline.llm import LocalAI
from pipeline.agenda_service import persist_agenda_items
from pipeline.agenda_resolver import resolve_agenda_items
from pipeline.models import AgendaItem
from pipeline.config import TIKA_MIN_EXTRACTED_CHARS_FOR_NO_OCR
from pipeline.extraction_service import reextract_catalog_content
from pipeline.indexer import reindex_catalog
from pipeline.content_hash import compute_content_hash
from pipeline.summary_quality import (
    analyze_source_text,
    build_low_signal_message,
    is_source_summarizable,
    is_source_topicable,
    is_summary_grounded,
)
from pipeline.startup_purge import run_startup_purge_if_enabled

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


@worker_ready.connect
def _run_startup_purge_on_worker_ready(sender=None, **kwargs):
    # The purge is env-gated and DB-lock protected so concurrent starters are safe.
    result = run_startup_purge_if_enabled()
    logger.info(f"startup_purge_result={result}")

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

        # Ensure we have a stable fingerprint for "is this summary stale?"
        content_hash = catalog.content_hash or compute_content_hash(catalog.content)
        quality = analyze_source_text(catalog.content)
        if not is_source_summarizable(quality):
            # We do not run Gemma on low-signal content because it tends to hallucinate.
            return {
                "status": "blocked_low_signal",
                "reason": build_low_signal_message(quality),
                "summary": None,
            }

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
        is_fresh = bool(
            catalog.summary
            and content_hash
            and catalog.summary_source_hash
            and catalog.summary_source_hash == content_hash
        )
        if (not force) and is_fresh:
            return {"status": "cached", "summary": catalog.summary}
        if (not force) and catalog.summary and not is_fresh:
            # Keep the old summary visible, but mark it as out-of-date.
            return {"status": "stale", "summary": catalog.summary}

        # If agenda items already exist, prefer a deterministic agenda-style summary instead
        # of relying entirely on the LLM. This is fast, stable, and avoids "how to attend"
        # boilerplate dominating the output.
        #
        # This is intentionally simple: we list the first few agenda item titles in order.
        used_model_summary = True
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
                    used_model_summary = False
                else:
                    summary = local_ai.summarize(catalog.content, doc_kind=doc_kind)
            else:
                summary = local_ai.summarize(catalog.content, doc_kind=doc_kind)
        else:
            summary = local_ai.summarize(catalog.content, doc_kind=doc_kind)
        
        # Retry instead of storing an empty summary.
        if summary is None:
            raise RuntimeError("AI Summarization returned None (Model missing or error)")

        # Guardrail: block ungrounded model claims (deterministic agenda-title summaries are exempt).
        if used_model_summary:
            grounding = is_summary_grounded(summary, catalog.content)
            if not grounding.is_grounded:
                reason = (
                    "Generated summary appears unsupported by extracted text. "
                    f"(coverage={grounding.coverage:.2f})"
                )
                return {
                    "status": "blocked_ungrounded",
                    "reason": reason,
                    "unsupported_claims": grounding.unsupported_claims[:3],
                    "summary": None,
                }
        
        # Update DB
        catalog.summary = summary
        catalog.content_hash = content_hash
        catalog.summary_source_hash = content_hash
        db.commit()

        # Best-effort: update the search index for just this catalog so stale flags
        # and snippets stay in sync for future searches.
        try:
            reindex_catalog(catalog_id)
        except Exception:
            pass
        
        logger.info(f"Summarization complete for Catalog ID {catalog_id}")
        return {"status": "complete", "summary": summary}

    except (SQLAlchemyError, RuntimeError, ValueError) as e:
        logger.error(f"Task failed: {e}")
        db.rollback()
        raise self.retry(exc=e, countdown=60)
    finally:
        db.close()


@app.task(bind=True, max_retries=3)
def generate_topics_task(self, catalog_id: int, force: bool = False, max_corpus_docs: int = 600):
    """
    Background task: (re)generate topic tags for a single catalog.

    Topics are derived from extracted text, so we tie them to Catalog.content_hash.
    This task uses a bounded per-city corpus to keep runtime predictable.
    """
    db = SessionLocal()
    try:
        catalog = db.get(Catalog, catalog_id)
        if not catalog or not catalog.content:
            return {"error": "No content to tag"}

        content_hash = catalog.content_hash or compute_content_hash(catalog.content)
        quality = analyze_source_text(catalog.content)
        if not is_source_topicable(quality):
            # We keep existing topics untouched and ask the user to improve extraction first.
            return {
                "status": "blocked_low_signal",
                "reason": build_low_signal_message(quality),
                "topics": [],
            }

        is_fresh = bool(
            catalog.topics is not None
            and content_hash
            and catalog.topics_source_hash
            and catalog.topics_source_hash == content_hash
        )
        if (not force) and is_fresh:
            return {"status": "cached", "topics": catalog.topics}
        if (not force) and catalog.topics is not None and not is_fresh:
            return {"status": "stale", "topics": catalog.topics}

        doc = db.query(Document).filter_by(catalog_id=catalog_id).first()
        if not doc:
            return {"error": "Document not linked to catalog"}

        # Reuse the same sanitation rules as the batch topic worker.
        from pipeline.topic_worker import _sanitize_text_for_topics
        from pipeline.config import (
            MAX_CONTENT_LENGTH,
            TFIDF_MAX_DF,
            TFIDF_MIN_DF,
            TFIDF_NGRAM_RANGE,
            TFIDF_MAX_FEATURES,
        )
        from sklearn.feature_extraction.text import TfidfVectorizer
        import numpy as np

        # Build a bounded, same-city corpus so TF-IDF weights are meaningful but fast.
        rows = (
            db.query(Catalog.id, Catalog.content)
            .join(Document, Document.catalog_id == Catalog.id)
            .filter(Document.place_id == doc.place_id, Catalog.content.isnot(None), Catalog.content != "")
            .order_by(Catalog.id.desc())
            .limit(max_corpus_docs)
            .all()
        )
        if not rows:
            return {"error": "No corpus available for topic tagging"}

        ids = [r[0] for r in rows]
        corpus = [_sanitize_text_for_topics((r[1] or "")[:MAX_CONTENT_LENGTH]) for r in rows]

        vectorizer = TfidfVectorizer(
            max_df=TFIDF_MAX_DF,
            min_df=TFIDF_MIN_DF,
            ngram_range=TFIDF_NGRAM_RANGE,
            max_features=TFIDF_MAX_FEATURES,
            stop_words="english",
        )
        tfidf = vectorizer.fit_transform(corpus)
        feature_names = vectorizer.get_feature_names_out()

        try:
            idx = ids.index(catalog_id)
        except ValueError:
            # The target doc might be older than our corpus window; include it explicitly.
            target_text = _sanitize_text_for_topics((catalog.content or "")[:MAX_CONTENT_LENGTH])
            corpus.insert(0, target_text)
            ids.insert(0, catalog_id)
            tfidf = vectorizer.fit_transform(corpus)
            feature_names = vectorizer.get_feature_names_out()
            idx = 0

        row = tfidf[idx].toarray().ravel()
        if row.size == 0:
            keywords = []
        else:
            top_idx = np.argsort(row)[::-1][:5]
            keywords = [feature_names[i].title() for i in top_idx if row[i] > 0]

        catalog.topics = keywords
        catalog.content_hash = content_hash
        catalog.topics_source_hash = content_hash
        db.commit()

        try:
            reindex_catalog(catalog_id)
        except Exception:
            pass

        return {"status": "complete", "topics": keywords}
    except (SQLAlchemyError, RuntimeError, ValueError) as e:
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


@app.task(bind=True, max_retries=3)
def extract_text_task(self, catalog_id: int, force: bool = False, ocr_fallback: bool = False):
    """
    Background task: re-extract a catalog's text from the already-downloaded file.

    This is intentionally "no download" and single-catalog scoped:
    - It only reads Catalog.location on disk.
    - It updates Catalog.content in the DB.
    - It reindexes just this catalog into Meilisearch.
    """
    db = SessionLocal()
    try:
        catalog = db.get(Catalog, catalog_id)
        result = reextract_catalog_content(
            catalog,
            force=force,
            ocr_fallback=ocr_fallback,
            min_chars=TIKA_MIN_EXTRACTED_CHARS_FOR_NO_OCR,
        )
        if "error" in result:
            # Only retry for transient extraction failures. Missing files / unsafe paths
            # should return immediately so the user can take action.
            transient = result["error"].lower() in {
                "extraction returned empty text",
            }
            if transient:
                raise RuntimeError(result["error"])
            return result

        db.commit()

        # Best-effort: update the search index for just this catalog.
        try:
            reindex_catalog(catalog_id)
        except Exception as e:
            # If reindexing fails, keep the extracted text (DB is source of truth).
            return {**result, "reindex_error": str(e)}

        return result
    except (SQLAlchemyError, RuntimeError, ValueError) as e:
        db.rollback()
        raise self.retry(exc=e, countdown=60)
    finally:
        db.close()

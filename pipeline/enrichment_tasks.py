from sqlalchemy.exc import SQLAlchemyError

from pipeline.celery_app import app
from pipeline.content_hash import compute_content_hash
from pipeline.indexer import reindex_catalog
from pipeline.models import Catalog, Document, Place
from pipeline.summary_quality import (
    analyze_source_text,
    build_low_signal_message,
    is_source_topicable,
)
from pipeline.task_runtime import task_session
from pipeline.task_agenda_titles import _extract_agenda_titles_from_text as _extract_agenda_titles_from_text
from pipeline.text_cleaning import postprocess_extracted_text
from pipeline.topic_generation import TopicGenerationTaskServices, run_generate_topics_task_family


def SessionLocal():
    return task_session()


def _topic_generation_task_services() -> TopicGenerationTaskServices:
    return TopicGenerationTaskServices(
        catalog_model=Catalog,
        document_model=Document,
        place_model=Place,
        compute_content_hash=compute_content_hash,
        analyze_source_text=analyze_source_text,
        is_source_topicable=is_source_topicable,
        build_low_signal_message=build_low_signal_message,
        postprocess_extracted_text=postprocess_extracted_text,
        extract_agenda_titles_from_text=_extract_agenda_titles_from_text,
        reindex_catalog=reindex_catalog,
    )


@app.task(bind=True, max_retries=3, name="enrichment.generate_topics")
def generate_topics_task(self, catalog_id: int, force: bool = False, max_corpus_docs: int = 600):
    """
    Background task: (re)generate topic tags for a single catalog.
    """
    db = SessionLocal()
    try:
        return run_generate_topics_task_family(
            db,
            catalog_id,
            force=force,
            max_corpus_docs=max_corpus_docs,
            services=_topic_generation_task_services(),
        )
    except (SQLAlchemyError, RuntimeError, MemoryError, ValueError) as exc:
        db.rollback()
        raise self.retry(exc=exc, countdown=60)
    finally:
        db.close()

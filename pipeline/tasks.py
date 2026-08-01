from celery.signals import worker_ready
from sqlalchemy.exc import SQLAlchemyError

from pipeline import lineage_task_support
from pipeline import llm
from pipeline import metrics as _worker_metrics  # noqa: F401
from pipeline import task_agenda_segmentation
from pipeline import task_runtime
from pipeline import task_startup
from pipeline import task_summary_generation
from pipeline import task_text_extraction
from pipeline import task_vote_extraction
from pipeline.celery_app import app


@worker_ready.connect
def _run_startup_purge_on_worker_ready(sender=None, **_signal_kwargs):
    task_startup.run_startup_purge_on_worker_ready(sender)


@app.task(bind=True, max_retries=3)
def generate_summary_task(self, catalog_id: int, force: bool = False):
    db = task_runtime.task_session()
    try:
        task_runtime.logger.info(f"Starting summarization for Catalog ID {catalog_id}")
        result = task_summary_generation.generate_catalog_summary(db, catalog_id, force=force)
        if result.get("status") == "complete":
            task_runtime.logger.info(f"Summarization complete for Catalog ID {catalog_id}")
        return result
    except llm.LocalAIConfigError as e:
        task_runtime.logger.critical(f"LocalAI misconfiguration: {e}")
        db.rollback()
        return {"status": "error", "error": str(e)}
    except (SQLAlchemyError, RuntimeError, ValueError) as e:
        task_runtime.logger.error(f"Task failed: {e}")
        db.rollback()
        raise self.retry(exc=e, countdown=60)
    finally:
        db.close()


@app.task(bind=True, max_retries=3)
def segment_agenda_task(self, catalog_id: int):
    db = task_runtime.task_session()
    try:
        task_runtime.logger.info(f"Starting segmentation for Catalog ID {catalog_id}")
        local_ai = llm.LocalAI()
        return task_agenda_segmentation.run_segment_agenda_task_family(db, catalog_id, local_ai=local_ai)
    except (SQLAlchemyError, RuntimeError, KeyError, ValueError) as e:
        task_runtime.logger.error(f"Task failed: {e}")
        db.rollback()
        try:
            task_agenda_segmentation.persist_agenda_segmentation_failure_status(db, catalog_id, str(e))
        except Exception:
            db.rollback()
        raise self.retry(exc=e, countdown=60)
    finally:
        db.close()


@app.task(bind=True, max_retries=3)
def extract_votes_task(self, catalog_id: int, force: bool = False):
    db = task_runtime.task_session()
    local_ai = llm.LocalAI()
    try:
        return task_vote_extraction.run_extract_votes_task_family(db, catalog_id, force=force, local_ai=local_ai)
    except (SQLAlchemyError, RuntimeError, ValueError) as e:
        task_runtime.logger.error(f"Vote extraction task failed: {e}")
        db.rollback()
        raise self.retry(exc=e, countdown=60)
    finally:
        db.close()


@app.task(bind=True, max_retries=3)
def extract_text_task(self, catalog_id: int, force: bool = False, ocr_fallback: bool = False):
    db = task_runtime.task_session()
    try:
        return task_text_extraction.run_extract_text_task_family(
            db,
            catalog_id,
            force=force,
            ocr_fallback=ocr_fallback,
        )
    except (SQLAlchemyError, RuntimeError, ValueError) as e:
        db.rollback()
        raise self.retry(exc=e, countdown=60)
    finally:
        db.close()


@app.task(bind=True, max_retries=3)
def compute_lineage_task(self):
    db = task_runtime.task_session()
    try:
        return lineage_task_support.run_lineage_recompute(db)
    except (SQLAlchemyError, RuntimeError, ValueError) as e:
        db.rollback()
        task_runtime.logger.error("compute_lineage_task failed: %s", e)
        raise self.retry(exc=e, countdown=30)
    finally:
        db.close()


@app.task(bind=True, max_retries=1)
def compute_lineage_for_catalog_task(self, catalog_id: int):
    _ = catalog_id
    return compute_lineage_task.run(self)

from typing import Any, Callable

from celery.signals import worker_ready
from sqlalchemy.exc import SQLAlchemyError

from pipeline import metrics as _worker_metrics  # noqa: F401
from pipeline import task_facade_helpers
from pipeline.agenda_service import persist_agenda_items
from pipeline.agenda_resolver import has_viable_structured_agenda_source, resolve_agenda_items
from pipeline.backlog_maintenance import (
    build_agenda_summary_input_bundle,
    build_deterministic_agenda_summary_payloads,
    persist_agenda_summary,
    summarize_catalog_with_maintenance_mode,
)
from pipeline.celery_app import app
from pipeline.config import (
    LOCAL_AI_ALLOW_MULTIPROCESS,
    LOCAL_AI_BACKEND,
    ENABLE_VOTE_EXTRACTION,
    LOCAL_AI_REQUIRE_SOLO_POOL,
    TIKA_MIN_EXTRACTED_CHARS_FOR_NO_OCR,
)
from pipeline.content_hash import compute_content_hash
from pipeline.document_kinds import normalize_summary_doc_kind
from pipeline.extraction_service import reextract_catalog_content
from pipeline.indexer import reindex_catalog
from pipeline.laserfiche_error_pages import classify_catalog_bad_content
from pipeline.runtime_guardrails import local_ai_runtime_guardrail_message
from pipeline.llm import LocalAI, LocalAIConfigError
from pipeline.lineage_task_support import run_lineage_recompute
from pipeline.models import Document
from pipeline.semantic_tasks import embed_catalog_task
from pipeline.startup_purge import run_startup_purge_if_enabled
from pipeline.summary_freshness import compute_summary_source_hash, is_summary_fresh
from pipeline.summary_quality import analyze_source_text, build_low_signal_message, is_source_summarizable, is_summary_grounded
from pipeline.task_agenda_titles import _extract_agenda_titles_from_text as _extract_agenda_titles_from_text
from pipeline.task_runtime import logger, task_session
from pipeline.task_startup import (
    get_celery_pool_from_argv as get_celery_pool_from_argv_impl,
    run_startup_purge_on_worker_ready as run_startup_purge_on_worker_ready_impl,
)
from pipeline.text_cleaning import postprocess_extracted_text
from pipeline.vote_extractor import run_vote_extraction_for_catalog

_TASK_FACADE_DEPENDENCIES = (
    build_agenda_summary_input_bundle, build_deterministic_agenda_summary_payloads, persist_agenda_summary,
    summarize_catalog_with_maintenance_mode, classify_catalog_bad_content, persist_agenda_items,
    has_viable_structured_agenda_source, resolve_agenda_items, TIKA_MIN_EXTRACTED_CHARS_FOR_NO_OCR,
    ENABLE_VOTE_EXTRACTION, reextract_catalog_content, reindex_catalog, compute_content_hash,
    normalize_summary_doc_kind, compute_summary_source_hash, is_summary_fresh, analyze_source_text,
    build_low_signal_message, is_source_summarizable, is_summary_grounded, postprocess_extracted_text,
    run_vote_extraction_for_catalog, embed_catalog_task, Document,
)


def SessionLocal():
    return task_session()


def _summary_doc_kind_subquery(db):
    return task_facade_helpers._summary_doc_kind_subquery(db)


def select_catalog_ids_for_summary_hydration(db, limit: int | None = None, city: str | None = None) -> list[int]:
    return task_facade_helpers.select_catalog_ids_for_summary_hydration(db, limit=limit, city=city)


def _summary_doc_kind_map(db, catalog_ids: list[int]) -> dict[int, str]:
    return task_facade_helpers._summary_doc_kind_map(db, catalog_ids)


def _enqueue_embed_catalogs(catalog_ids: list[int]) -> dict[str, object]:
    return task_facade_helpers._enqueue_embed_catalogs(catalog_ids)


def run_summary_hydration_backfill(
    force: bool = False,
    limit: int | None = None,
    city: str | None = None,
    *,
    summary_timeout_seconds: int | None = None,
    summary_fallback_mode: str = "none",
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
    progress_every: int = 25,
) -> dict[str, int]:
    return task_facade_helpers.run_summary_hydration_backfill(
        globals(),
        force=force,
        limit=limit,
        city=city,
        summary_timeout_seconds=summary_timeout_seconds,
        summary_fallback_mode=summary_fallback_mode,
        progress_callback=progress_callback,
        progress_every=progress_every,
    )


def _get_celery_pool_from_argv(argv: list[str]) -> str | None:
    return get_celery_pool_from_argv_impl(argv)


@worker_ready.connect
def _run_startup_purge_on_worker_ready(sender=None, **kwargs):
    _ = kwargs
    run_startup_purge_on_worker_ready_impl(
        sender,
        backend=LOCAL_AI_BACKEND,
        allow_multiprocess=LOCAL_AI_ALLOW_MULTIPROCESS,
        require_solo_pool=LOCAL_AI_REQUIRE_SOLO_POOL,
        guardrail_message_builder=local_ai_runtime_guardrail_message,
        startup_purge_callable=run_startup_purge_if_enabled,
    )


def _run_extract_text_task_family(db, catalog_id: int, *, force: bool, ocr_fallback: bool) -> dict[str, Any]:
    return task_facade_helpers.run_extract_text_task_family(globals(), db, catalog_id, force=force, ocr_fallback=ocr_fallback)


def _run_extract_votes_task_family(db, catalog_id: int, *, force: bool, local_ai: LocalAI) -> dict[str, Any]:
    return task_facade_helpers.run_extract_votes_task_family(globals(), db, catalog_id, force=force, local_ai=local_ai)


def _agenda_segmentation_task_services():
    return task_facade_helpers.agenda_segmentation_task_services(globals())


def _summary_generation_task_services():
    return task_facade_helpers.summary_generation_task_services(globals())


def _run_summary_generation_side_effects(catalog_id: int) -> dict[str, int]:
    return task_facade_helpers.run_summary_generation_side_effects(globals(), catalog_id)


def _record_agenda_segmentation_status(catalog, *, status: str, item_count: int, error_message: str | None) -> None:
    task_facade_helpers.record_agenda_segmentation_status(
        catalog, status=status, item_count=item_count, error_message=error_message
    )


def _run_post_segmentation_vote_extraction(db, *, local_ai: LocalAI, catalog, doc, created_items: list[Any]) -> dict[str, Any]:
    return task_facade_helpers.run_post_segmentation_vote_extraction(
        globals(), db, local_ai=local_ai, catalog=catalog, doc=doc, created_items=created_items
    )


def _persist_agenda_segmentation_failure_status(db, catalog_id: int, error_message: str) -> None:
    task_facade_helpers.persist_agenda_segmentation_failure_status(db, catalog_id, error_message)


def _run_segment_agenda_task_family(db, catalog_id: int, *, local_ai: LocalAI) -> dict[str, Any]:
    return task_facade_helpers.run_segment_agenda_task_family(globals(), db, catalog_id, local_ai=local_ai)


def _run_generate_summary_task_family(db, catalog_id: int, *, force: bool) -> dict[str, Any]:
    return task_facade_helpers.run_generate_summary_task_family(globals(), db, catalog_id, force=force)


@app.task(bind=True, max_retries=3)
def generate_summary_task(self, catalog_id: int, force: bool = False):
    db = SessionLocal()
    try:
        logger.info(f"Starting summarization for Catalog ID {catalog_id}")
        result = _run_generate_summary_task_family(db, catalog_id, force=force)
        if result.get("status") == "complete":
            logger.info(f"Summarization complete for Catalog ID {catalog_id}")
        return result
    except LocalAIConfigError as e:
        logger.critical(f"LocalAI misconfiguration: {e}")
        db.rollback()
        return {"status": "error", "error": str(e)}
    except (SQLAlchemyError, RuntimeError, ValueError) as e:
        logger.error(f"Task failed: {e}")
        db.rollback()
        raise self.retry(exc=e, countdown=60)
    finally:
        db.close()


@app.task(bind=True, max_retries=3)
def segment_agenda_task(self, catalog_id: int):
    db = SessionLocal()
    try:
        logger.info(f"Starting segmentation for Catalog ID {catalog_id}")
        local_ai = LocalAI()
        return _run_segment_agenda_task_family(db, catalog_id, local_ai=local_ai)
    except LocalAIConfigError as e:
        logger.critical(f"LocalAI misconfiguration: {e}")
        db.rollback()
        try:
            _persist_agenda_segmentation_failure_status(db, catalog_id, str(e))
        except Exception:
            db.rollback()
        return {"status": "error", "error": str(e)}
    except (SQLAlchemyError, RuntimeError, KeyError, ValueError) as e:
        logger.error(f"Task failed: {e}")
        db.rollback()
        try:
            _persist_agenda_segmentation_failure_status(db, catalog_id, str(e))
        except Exception:
            db.rollback()
        raise self.retry(exc=e, countdown=60)
    finally:
        db.close()


@app.task(bind=True, max_retries=3)
def extract_votes_task(self, catalog_id: int, force: bool = False):
    db = SessionLocal()
    local_ai = LocalAI()
    try:
        return _run_extract_votes_task_family(db, catalog_id, force=force, local_ai=local_ai)
    except LocalAIConfigError as e:
        logger.critical(f"LocalAI misconfiguration: {e}")
        db.rollback()
        return {"status": "error", "error": str(e)}
    except (SQLAlchemyError, RuntimeError, ValueError) as e:
        logger.error(f"Vote extraction task failed: {e}")
        db.rollback()
        raise self.retry(exc=e, countdown=60)
    finally:
        db.close()


@app.task(bind=True, max_retries=3)
def extract_text_task(self, catalog_id: int, force: bool = False, ocr_fallback: bool = False):
    db = SessionLocal()
    try:
        return _run_extract_text_task_family(db, catalog_id, force=force, ocr_fallback=ocr_fallback)
    except (SQLAlchemyError, RuntimeError, ValueError) as e:
        db.rollback()
        raise self.retry(exc=e, countdown=60)
    finally:
        db.close()


@app.task(bind=True, max_retries=3)
def compute_lineage_task(self):
    db = SessionLocal()
    try:
        return run_lineage_recompute(db)
    except (SQLAlchemyError, RuntimeError, ValueError) as e:
        db.rollback()
        logger.error("compute_lineage_task failed: %s", e)
        raise self.retry(exc=e, countdown=30)
    finally:
        db.close()


@app.task(bind=True, max_retries=1)
def compute_lineage_for_catalog_task(self, catalog_id: int):
    _ = catalog_id
    return compute_lineage_task.run(self)

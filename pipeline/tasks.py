from celery.signals import worker_ready
from sqlalchemy.exc import SQLAlchemyError
from typing import Any, Callable

from pipeline.backlog_maintenance import (
    build_agenda_summary_input_bundle,
    build_deterministic_agenda_summary_payloads,
    persist_agenda_summary,
    summarize_catalog_with_maintenance_mode,
)
from pipeline.laserfiche_error_pages import classify_catalog_bad_content
from pipeline.models import Catalog, Document
from pipeline.llm import LocalAI, LocalAIConfigError
from pipeline.agenda_service import persist_agenda_items
from pipeline.agenda_resolver import has_viable_structured_agenda_source, resolve_agenda_items
from pipeline.models import AgendaItem
from pipeline.config import (
    TIKA_MIN_EXTRACTED_CHARS_FOR_NO_OCR,
    LOCAL_AI_ALLOW_MULTIPROCESS,
    LOCAL_AI_REQUIRE_SOLO_POOL,
    LOCAL_AI_BACKEND,
    ENABLE_VOTE_EXTRACTION,
)
from pipeline.extraction_service import reextract_catalog_content
from pipeline.indexer import reindex_catalog
from pipeline.content_hash import compute_content_hash
from pipeline.document_kinds import normalize_summary_doc_kind
from pipeline.summary_freshness import (
    compute_summary_source_hash,
    is_summary_fresh,
)
from pipeline.summary_quality import (
    analyze_source_text,
    build_low_signal_message,
    is_source_summarizable,
    is_summary_grounded,
)
from pipeline.text_cleaning import postprocess_extracted_text
from pipeline.runtime_guardrails import local_ai_runtime_guardrail_message
from pipeline.startup_purge import run_startup_purge_if_enabled
from pipeline.summary_backfill import (
    _summary_doc_kind_map as _summary_doc_kind_map_impl,
    _summary_doc_kind_subquery as _summary_doc_kind_subquery_impl,
    _enqueue_embed_catalogs as _enqueue_embed_catalogs_impl,
    run_summary_hydration_backfill as run_summary_hydration_backfill_impl,
    select_catalog_ids_for_summary_hydration as select_catalog_ids_for_summary_hydration_impl,
)
from pipeline.lineage_task_support import run_lineage_recompute
from pipeline.task_agenda_titles import _extract_agenda_titles_from_text as _extract_agenda_titles_from_text
from pipeline.task_agenda_segmentation import (
    AgendaSegmentationTaskServices,
    persist_agenda_segmentation_failure_status as persist_agenda_segmentation_failure_status_impl,
    record_agenda_segmentation_status as record_agenda_segmentation_status_impl,
    run_post_segmentation_vote_extraction as run_post_segmentation_vote_extraction_impl,
    run_segment_agenda_task_family as run_segment_agenda_task_family_impl,
)
from pipeline.task_startup import (
    get_celery_pool_from_argv as get_celery_pool_from_argv_impl,
    run_startup_purge_on_worker_ready as run_startup_purge_on_worker_ready_impl,
)
from pipeline.task_summary_generation import (
    SummaryGenerationTaskServices,
    run_generate_summary_task_family as run_generate_summary_task_family_impl,
    run_summary_generation_side_effects as run_summary_generation_side_effects_impl,
)
from pipeline.task_text_extraction import run_extract_text_task_family as run_extract_text_task_family_impl
from pipeline.task_runtime import logger, task_session
from pipeline.task_vote_extraction import run_extract_votes_task_family as run_extract_votes_task_family_impl
from pipeline.vote_extractor import run_vote_extraction_for_catalog
from pipeline.celery_app import app
from pipeline.semantic_tasks import embed_catalog_task

# Register worker metrics (safe in non-worker contexts; the HTTP server only starts
# when TC_WORKER_METRICS_PORT is set and the Celery worker is ready).
from pipeline import metrics as _worker_metrics  # noqa: F401


def SessionLocal():
    return task_session()


def _summary_doc_kind_subquery(db):
    return _summary_doc_kind_subquery_impl(db)


def select_catalog_ids_for_summary_hydration(db, limit: int | None = None, city: str | None = None) -> list[int]:
    return select_catalog_ids_for_summary_hydration_impl(db, limit=limit, city=city)


def _summary_doc_kind_map(db, catalog_ids: list[int]) -> dict[int, str]:
    return _summary_doc_kind_map_impl(db, catalog_ids)


def _enqueue_embed_catalogs(catalog_ids: list[int]) -> dict[str, object]:
    return _enqueue_embed_catalogs_impl(catalog_ids)


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
    return run_summary_hydration_backfill_impl(
        force=force,
        limit=limit,
        city=city,
        summary_timeout_seconds=summary_timeout_seconds,
        summary_fallback_mode=summary_fallback_mode,
        progress_callback=progress_callback,
        progress_every=progress_every,
        generate_summary_callable=lambda catalog_id: generate_summary_task.run(catalog_id, force=force),
        session_factory=SessionLocal,
        select_catalog_ids_callable=select_catalog_ids_for_summary_hydration,
        summary_doc_kind_map_callable=_summary_doc_kind_map,
        agenda_summary_batch_builder=build_deterministic_agenda_summary_payloads,
        summarize_catalog_callable=summarize_catalog_with_maintenance_mode,
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


def _run_extract_text_task_family(
    db,
    catalog_id: int,
    *,
    force: bool,
    ocr_fallback: bool,
) -> dict[str, Any]:
    """
    Keep the historical pipeline.tasks patch seam around the extracted text helper.
    """
    return run_extract_text_task_family_impl(
        db,
        catalog_id,
        force=force,
        ocr_fallback=ocr_fallback,
        min_chars=TIKA_MIN_EXTRACTED_CHARS_FOR_NO_OCR,
        reextract_catalog_content_callable=reextract_catalog_content,
        reindex_catalog_callable=reindex_catalog,
    )


def _run_extract_votes_task_family(
    db,
    catalog_id: int,
    *,
    force: bool,
    local_ai: LocalAI,
) -> dict[str, Any]:
    """
    Keep the historical pipeline.tasks patch seam around the extracted vote helper.
    """
    return run_extract_votes_task_family_impl(
        db,
        catalog_id,
        force=force,
        local_ai=local_ai,
        vote_extraction_enabled=ENABLE_VOTE_EXTRACTION,
        run_vote_extraction_for_catalog_callable=run_vote_extraction_for_catalog,
        reindex_catalog_callable=reindex_catalog,
    )


def _agenda_segmentation_task_services() -> AgendaSegmentationTaskServices:
    return AgendaSegmentationTaskServices(
        classify_catalog_bad_content=classify_catalog_bad_content,
        has_viable_structured_agenda_source=has_viable_structured_agenda_source,
        resolve_agenda_items=resolve_agenda_items,
        persist_agenda_items=persist_agenda_items,
        run_vote_extraction_for_catalog=run_vote_extraction_for_catalog,
        reindex_catalog=reindex_catalog,
        vote_extraction_enabled=ENABLE_VOTE_EXTRACTION,
    )


def _summary_generation_task_services() -> SummaryGenerationTaskServices:
    return SummaryGenerationTaskServices(
        local_ai_factory=LocalAI,
        classify_catalog_bad_content=classify_catalog_bad_content,
        compute_content_hash=compute_content_hash,
        normalize_summary_doc_kind=normalize_summary_doc_kind,
        analyze_source_text=analyze_source_text,
        is_source_summarizable=is_source_summarizable,
        build_low_signal_message=build_low_signal_message,
        build_agenda_summary_input_bundle=build_agenda_summary_input_bundle,
        is_summary_fresh=is_summary_fresh,
        compute_summary_source_hash=compute_summary_source_hash,
        postprocess_extracted_text=postprocess_extracted_text,
        is_summary_grounded=is_summary_grounded,
        persist_agenda_summary=persist_agenda_summary,
        reindex_catalog=reindex_catalog,
        embed_catalog=embed_catalog_task.delay,
    )


def _run_summary_generation_side_effects(catalog_id: int) -> dict[str, int]:
    """
    Keep the historical pipeline.tasks patch seam around summary side effects.
    """
    return run_summary_generation_side_effects_impl(
        catalog_id,
        services=_summary_generation_task_services(),
    )


def _record_agenda_segmentation_status(
    catalog: Catalog,
    *,
    status: str,
    item_count: int,
    error_message: str | None,
) -> None:
    """
    Keep the historical pipeline.tasks patch seam around segmentation status writes.
    """
    record_agenda_segmentation_status_impl(
        catalog,
        status=status,
        item_count=item_count,
        error_message=error_message,
    )


def _run_post_segmentation_vote_extraction(
    db,
    *,
    local_ai: LocalAI,
    catalog: Catalog,
    doc: Document,
    created_items: list[AgendaItem],
) -> dict[str, Any]:
    """
    Keep the historical pipeline.tasks patch seam around post-segmentation votes.
    """
    return run_post_segmentation_vote_extraction_impl(
        db,
        local_ai=local_ai,
        catalog=catalog,
        doc=doc,
        created_items=created_items,
        services=_agenda_segmentation_task_services(),
    )


def _persist_agenda_segmentation_failure_status(
    db,
    catalog_id: int,
    error_message: str,
) -> None:
    """
    Keep the historical pipeline.tasks patch seam around failure persistence.
    """
    persist_agenda_segmentation_failure_status_impl(db, catalog_id, error_message)


def _run_segment_agenda_task_family(
    db,
    catalog_id: int,
    *,
    local_ai: LocalAI,
) -> dict[str, Any]:
    """
    Keep the historical pipeline.tasks patch seam around the extracted segmentation helper.
    """
    return run_segment_agenda_task_family_impl(
        db,
        catalog_id,
        local_ai=local_ai,
        services=_agenda_segmentation_task_services(),
    )


def _run_generate_summary_task_family(
    db,
    catalog_id: int,
    *,
    force: bool,
) -> dict[str, Any]:
    """
    Keep the historical pipeline.tasks patch seam around the extracted summary helper.
    """
    return run_generate_summary_task_family_impl(
        db,
        catalog_id,
        force=force,
        services=_summary_generation_task_services(),
    )


@app.task(bind=True, max_retries=3)
def generate_summary_task(self, catalog_id: int, force: bool = False):
    """
    Background task: generate and store a catalog summary.
    """
    db = SessionLocal()
    
    try:
        logger.info(f"Starting summarization for Catalog ID {catalog_id}")
        result = _run_generate_summary_task_family(
            db,
            catalog_id,
            force=force,
        )
        if result.get("status") == "complete":
            logger.info(f"Summarization complete for Catalog ID {catalog_id}")
        return result

    except LocalAIConfigError as e:
        # Configuration errors are not transient; do not retry.
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
    """
    Background task: segment catalog text into agenda items.
    """
    db = SessionLocal()
    
    try:
        logger.info(f"Starting segmentation for Catalog ID {catalog_id}")
        local_ai = LocalAI()
        return _run_segment_agenda_task_family(
            db,
            catalog_id,
            local_ai=local_ai,
        )

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
        # Best-effort: persist failure status so batch workers don't spin forever.
        try:
            _persist_agenda_segmentation_failure_status(db, catalog_id, str(e))
        except Exception:
            db.rollback()
        raise self.retry(exc=e, countdown=60)
    finally:
        db.close()


@app.task(bind=True, max_retries=3)
def extract_votes_task(self, catalog_id: int, force: bool = False):
    """
    Background task: extract agenda-item outcomes/vote tallies from catalog text.
    """
    db = SessionLocal()
    local_ai = LocalAI()

    try:
        return _run_extract_votes_task_family(
            db,
            catalog_id,
            force=force,
            local_ai=local_ai,
        )
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
    """
    Background task: re-extract a catalog's text from the already-downloaded file.

    This is intentionally "no download" and single-catalog scoped:
    - It only reads Catalog.location on disk.
    - It updates Catalog.content in the DB.
    - It reindexes just this catalog into Meilisearch.
    """
    db = SessionLocal()
    try:
        return _run_extract_text_task_family(
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
    """
    Recompute meeting-level lineage assignments from related_ids.
    """
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
    """
    Catalog-triggered lineage update wrapper.
    """
    _ = catalog_id
    return compute_lineage_task.run(self)

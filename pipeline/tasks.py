from celery.signals import worker_ready
from datetime import datetime, timezone
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
from pipeline.task_startup import (
    get_celery_pool_from_argv as get_celery_pool_from_argv_impl,
    run_startup_purge_on_worker_ready as run_startup_purge_on_worker_ready_impl,
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


def _run_summary_generation_side_effects(catalog_id: int) -> dict[str, int]:
    """
    Summary persistence is the source of truth; search and embedding side effects stay best-effort.
    """
    reindexed = 0
    reindex_failed = 0
    try:
        reindex_catalog(catalog_id)
        reindexed = 1
    except Exception as reindex_error:
        reindex_failed = 1
        logger.warning("summary_generation.reindex_failed catalog_id=%s error=%s", catalog_id, reindex_error)

    embed_enqueued = 0
    embed_dispatch_failed = 0
    try:
        embed_catalog_task.delay(catalog_id)
        embed_enqueued = 1
    except Exception as exc:
        logger.warning("embed_catalog_task.dispatch_failed catalog_id=%s error=%s", catalog_id, exc)
        embed_dispatch_failed = 1

    return {
        "reindexed": reindexed,
        "reindex_failed": reindex_failed,
        "embed_enqueued": embed_enqueued,
        "embed_dispatch_failed": embed_dispatch_failed,
    }


def _record_agenda_segmentation_status(
    catalog: Catalog,
    *,
    status: str,
    item_count: int,
    error_message: str | None,
) -> None:
    """
    Keep segmentation status writes explicit without introducing a generic task-state helper.
    """
    catalog.agenda_segmentation_status = status
    catalog.agenda_segmentation_item_count = item_count
    catalog.agenda_segmentation_attempted_at = datetime.now(timezone.utc)
    catalog.agenda_segmentation_error = error_message


def _run_post_segmentation_vote_extraction(
    db,
    *,
    local_ai: LocalAI,
    catalog: Catalog,
    doc: Document,
    created_items: list[AgendaItem],
) -> dict[str, Any]:
    """
    Vote extraction remains a non-gating post-segmentation stage in this task family.
    """
    if not ENABLE_VOTE_EXTRACTION:
        return {
            "status": "disabled",
            "processed_items": 0,
            "updated_items": 0,
            "skipped_items": 0,
            "failed_items": 0,
            "skip_reasons": {},
        }

    try:
        vote_counters = run_vote_extraction_for_catalog(
            db,
            local_ai,
            catalog,
            doc,
            force=False,
            agenda_items=created_items,
        )
        return {"status": "complete", **vote_counters}
    except Exception as vote_exc:
        logger.warning(
            "vote_extraction.post_segment_failed catalog_id=%s error=%s",
            catalog.id,
            vote_exc.__class__.__name__,
        )
        return {
            "status": "failed",
            "error": vote_exc.__class__.__name__,
            "processed_items": 0,
            "updated_items": 0,
            "skipped_items": 0,
            "failed_items": 0,
            "skip_reasons": {},
        }


def _persist_agenda_segmentation_failure_status(
    db,
    catalog_id: int,
    error_message: str,
) -> None:
    """
    Failure persistence is best-effort and stays under task-wrapper ownership.
    """
    catalog = db.get(Catalog, catalog_id)
    if not catalog:
        return
    _record_agenda_segmentation_status(
        catalog,
        status="failed",
        item_count=0,
        error_message=error_message[:500],
    )
    db.commit()


def _run_segment_agenda_task_family(
    db,
    catalog_id: int,
    *,
    local_ai: LocalAI,
) -> dict[str, Any]:
    """
    Run agenda segmentation for one catalog while leaving retries and failure persistence to the task.
    """
    catalog = db.get(Catalog, catalog_id)

    if not catalog or not catalog.content:
        return {"error": "No content"}

    doc = db.query(Document).filter_by(catalog_id=catalog_id).first()
    if not doc:
        return {"error": "Document not linked to event"}

    classification = classify_catalog_bad_content(
        catalog,
        document_category=getattr(doc, "category", None),
        include_document_shape=True,
        has_viable_structured_source=has_viable_structured_agenda_source(db, catalog, doc),
    )
    if classification:
        _record_agenda_segmentation_status(
            catalog,
            status="failed",
            item_count=0,
            error_message=classification.reason,
        )
        db.commit()
        return {"status": "error", "error": classification.reason}

    resolved = resolve_agenda_items(db, catalog, doc, local_ai)
    items_data = resolved["items"]

    count = 0
    items_to_return = []
    if items_data:
        created_items = persist_agenda_items(db, catalog_id, doc.event_id, items_data)
        items_to_return = [
            {
                "title": item.title,
                "description": item.description,
                "order": item.order,
                "classification": item.classification,
                "result": item.result,
                "page_number": item.page_number,
                "source": resolved["source_used"],
            }
            for item in created_items
        ]
        count = len(items_to_return)
        vote_extraction = _run_post_segmentation_vote_extraction(
            db,
            local_ai=local_ai,
            catalog=catalog,
            doc=doc,
            created_items=created_items,
        )
        _record_agenda_segmentation_status(
            catalog,
            status="complete",
            item_count=count,
            error_message=None,
        )
        db.commit()
        try:
            reindex_catalog(catalog_id)
        except Exception as reindex_error:
            # Agenda items are already persisted, so targeted reindex remains best-effort.
            logger.warning("agenda_segmentation.reindex_failed catalog_id=%s error=%s", catalog_id, reindex_error)
    else:
        _record_agenda_segmentation_status(
            catalog,
            status="empty",
            item_count=0,
            error_message=None,
        )
        db.commit()
        vote_extraction = {
            "status": "skipped_no_items",
            "processed_items": 0,
            "updated_items": 0,
            "skipped_items": 0,
            "failed_items": 0,
            "skip_reasons": {},
        }

    logger.info(f"Segmentation complete: {count} items found (source={resolved['source_used']})")
    return {
        "status": "complete",
        "item_count": count,
        "items": items_to_return,
        "source_used": resolved["source_used"],
        "quality_score": resolved["quality_score"],
        "vote_extraction": vote_extraction,
    }


def _run_generate_summary_task_family(
    db,
    catalog_id: int,
    *,
    force: bool,
) -> dict[str, Any]:
    """
    Run summary generation for one catalog while leaving retry and session ownership to the task.
    """
    catalog = db.get(Catalog, catalog_id)

    # Decide how to summarize based on the *document type*.
    # Many cities publish agenda PDFs without corresponding minutes PDFs.
    # If we summarize an agenda using a "minutes" prompt, the output looks incorrect.
    doc = db.query(Document).filter_by(catalog_id=catalog_id).first()
    doc_kind = normalize_summary_doc_kind(doc.category if doc else "unknown")

    if not catalog:
        return {"error": "Catalog not found"}
    classification = classify_catalog_bad_content(catalog)
    if classification:
        return {"status": "error", "error": classification.reason}
    local_ai = LocalAI()

    # Ensure we have a stable fingerprint for "is this summary stale?"
    content_hash = compute_content_hash(catalog.content) if (catalog.content or "") else None
    if content_hash:
        catalog.content_hash = content_hash

    # Minutes/unknown summaries are grounded in extracted text, so we block low-signal inputs.
    # Agenda summaries are derived from segmented agenda items, so the extracted-text quality
    # gate is not the right control (Legistar items can be good even if PDF text is sparse).
    if doc_kind != "agenda":
        if not catalog.content:
            return {"error": "No content to summarize"}
        quality = analyze_source_text(catalog.content)
        if not is_source_summarizable(quality):
            # We do not run Gemma on low-signal content because it tends to hallucinate.
            return {
                "status": "blocked_low_signal",
                "reason": build_low_signal_message(quality),
                "summary": None,
            }

    # Agenda summaries are derived from segmented agenda items (not raw PDF text) so the
    # AI Summary and Structured Agenda tabs cannot drift.
    # Whether we should run the "summary must be lexically grounded in extracted text" check.
    # Agenda summaries are derived from structured items, so we do not ground against the PDF text.
    do_grounding_check = True
    agenda_items_hash = catalog.agenda_items_hash
    agenda_summary_bundle = None
    if doc_kind == "agenda":
        agenda_summary_bundle = build_agenda_summary_input_bundle(
            catalog=catalog,
            document=doc,
            agenda_items=(
                db.query(AgendaItem)
                .filter_by(catalog_id=catalog_id)
                .order_by(AgendaItem.order)
                .all()
            ),
            include_meeting_context=True,
        )
        if agenda_summary_bundle.get("status") != "ready":
            return agenda_summary_bundle
        agenda_items_hash = agenda_summary_bundle["agenda_items_hash"]
        if agenda_items_hash != catalog.agenda_items_hash:
            catalog.agenda_items_hash = agenda_items_hash

    # Return cached value when already summarized, unless the caller forces a refresh.
    #
    # Why have `force`?
    # Summaries are cached on the Catalog row. When we improve the prompt/cleanup logic,
    # old low-quality summaries won't change unless we regenerate them.
    is_fresh = is_summary_fresh(
        doc_kind,
        summary=catalog.summary,
        summary_source_hash=catalog.summary_source_hash,
        content_hash=content_hash,
        agenda_items_hash=agenda_items_hash,
    )
    if (not force) and is_fresh:
        return {"status": "cached", "summary": catalog.summary, "changed": False}
    if (not force) and catalog.summary and not is_fresh:
        # Keep the old summary visible, but mark it as out-of-date.
        return {"status": "stale", "summary": catalog.summary, "changed": False}

    if doc_kind == "agenda":
        # Use all available titles, bounded only by model context. If we must truncate,
        # we disclose it in the prompt requirements.
        summary = local_ai.summarize_agenda_items(
            meeting_title=agenda_summary_bundle["meeting_title"],
            meeting_date=agenda_summary_bundle["meeting_date"],
            items=agenda_summary_bundle["summary_items"],
            truncation_meta=agenda_summary_bundle["truncation_meta"],
        )
        # Agenda summaries are derived from structured titles, not raw text.
        do_grounding_check = False
    else:
        summary = local_ai.summarize(postprocess_extracted_text(catalog.content), doc_kind=doc_kind)

    # Retry instead of storing an empty summary.
    if summary is None:
        raise RuntimeError("AI Summarization returned None (Model missing or error)")

    # Guardrail: block ungrounded model claims (deterministic agenda-title summaries are exempt).
    if do_grounding_check:
        # Ground against the extracted text. This is conservative and may block on
        # paraphrases; if it becomes too strict for agenda-item summaries, we can
        # switch to grounding against the agenda-items payload instead.
        grounding = is_summary_grounded(summary, postprocess_extracted_text(catalog.content))
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

    if doc_kind == "agenda":
        persisted_summary = persist_agenda_summary(
            catalog=catalog,
            summary=summary,
            content_hash=agenda_summary_bundle["content_hash"],
            agenda_items_hash=agenda_summary_bundle["agenda_items_hash"],
        )
    else:
        prior_summary = catalog.summary
        prior_summary_source_hash = catalog.summary_source_hash
        summary_source_hash = compute_summary_source_hash(
            doc_kind,
            content_hash=content_hash,
            agenda_items_hash=agenda_items_hash,
        )
        catalog.summary = summary
        if content_hash:
            catalog.content_hash = content_hash
        if summary_source_hash:
            catalog.summary_source_hash = summary_source_hash
        persisted_summary = {
            "status": "complete",
            "summary": summary,
            "changed": bool(prior_summary != summary or prior_summary_source_hash != summary_source_hash),
        }
    db.commit()

    side_effects = _run_summary_generation_side_effects(catalog_id)
    return {
        "status": "complete",
        "summary": summary,
        "changed": bool(persisted_summary["changed"]),
        **side_effects,
    }

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

from celery.signals import worker_ready
import sys
import logging
import re
from datetime import datetime, timezone
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import and_, func, or_, text
from typing import Any, Callable

from pipeline.backlog_maintenance import (
    AGENDA_SUMMARY_BUNDLE_BUILD_MS,
    AGENDA_SUMMARY_EMBED_DISPATCH_MS,
    AGENDA_SUMMARY_PERSIST_MS,
    AGENDA_SUMMARY_REINDEX_MS,
    AGENDA_SUMMARY_RENDER_MS,
    build_agenda_summary_input_bundle,
    build_deterministic_agenda_summary_payload,
    build_deterministic_agenda_summary_payloads,
    persist_agenda_summary,
    summarize_catalog_with_maintenance_mode,
    summary_timeout_override,
)
from pipeline.laserfiche_error_pages import classify_catalog_bad_content
from pipeline.models import db_connect, Catalog, Document, Event
from pipeline.llm import LocalAI, LocalAIConfigError
from pipeline.agenda_service import persist_agenda_items
from pipeline.agenda_resolver import has_viable_structured_agenda_source, resolve_agenda_items
from pipeline.city_scope import source_aliases_for_city
from pipeline.models import AgendaItem
from pipeline.config import (
    TIKA_MIN_EXTRACTED_CHARS_FOR_NO_OCR,
    LOCAL_AI_ALLOW_MULTIPROCESS,
    LOCAL_AI_REQUIRE_SOLO_POOL,
    LOCAL_AI_BACKEND,
    ENABLE_VOTE_EXTRACTION,
    LINEAGE_MIN_EDGE_CONFIDENCE,
    LINEAGE_REQUIRE_MUTUAL_EDGES,
)
from pipeline.extraction_service import reextract_catalog_content
from pipeline.indexer import reindex_catalog, reindex_catalogs
from pipeline.content_hash import compute_content_hash
from pipeline.document_kinds import normalize_summary_doc_kind, summary_doc_kind_sql_expr
from pipeline.lineage_service import compute_lineage_assignments
from pipeline.metrics import record_lineage_recompute
from pipeline.profiling import apply_catalog_id_scope
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
from pipeline.vote_extractor import run_vote_extraction_for_catalog
from pipeline.celery_app import app
from pipeline.semantic_tasks import embed_catalog_task

# Register worker metrics (safe in non-worker contexts; the HTTP server only starts
# when TC_WORKER_METRICS_PORT is set and the Celery worker is ready).
from pipeline import metrics as _worker_metrics  # noqa: F401

# Setup logging
logger = logging.getLogger("celery-worker")


def _dedupe_titles_preserve_order(values):
    """
    Deduplicate extracted title candidates without reordering them.
    """
    seen = set()
    out = []
    for v in values or []:
        key = (v or "").strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(v.strip())
    return out


def _extract_agenda_titles_from_text(text: str, max_titles: int = 3):
    """
    Best-effort agenda title extraction from raw/flattened extracted text.

    Why this exists:
    Some "agenda" PDFs are tiny, header-heavy, or flattened into a single line.
    In those cases, an LLM summary often degenerates into boilerplate or headings.
    This heuristic keeps the output deterministic and city-agnostic.
    """
    if not text:
        return []

    # Page markers are useful for deep linking, but they make regex parsing noisier.
    value = re.sub(r"\[PAGE\s+\d+\]", "\n", text, flags=re.IGNORECASE)
    # Normalize runs of spaces/tabs without deleting letters.
    value = re.sub(r"[ \t]+", " ", value)

    titles = []

    def _looks_like_attendance_or_access_info(line: str) -> bool:
        """
        Skip "how to attend" boilerplate.

        Why:
        Many agendas include numbered participation instructions (email/phone/webinar).
        Those are not agenda *items* and should not drive summaries.
        """
        v = (line or "").strip().lower()
        if not v:
            return True
        needles = [
            "teleconference",
            "public participation",
            "email comments",
            "e-mail comments",
            "email address",
            "enter an email",
            "enter your email",
            "register",
            "webinar",
            "zoom",
            "webex",
            "teams",
            "passcode",
            "phone",
            "dial",
            "raise hand",
            "unmute",
            "mute",
            "last four digits",
            "time allotted",
            "limit your remarks",
            "browser",
            "microsoft edge",
            "internet explorer",
            "safari",
            "firefox",
            "chrome",
            "ada",
            "accommodation",
            "accessibility",
        ]
        return any(n in v for n in needles)

    # 1) Prefer true line-based numbering when available.
    for m in re.finditer(r"(?m)^\s*\d+\.\s+(.+?)\s*$", value):
        title = (m.group(1) or "").strip()
        if not title or len(title) < 10:
            continue
        if _looks_like_attendance_or_access_info(title):
            continue
        titles.append(title)
        if len(titles) >= max_titles:
            break

    # 2) Fallback: split by inline numbering when extraction collapsed line breaks.
    if len(titles) < max_titles:
        parts = re.split(r"\b(\d{1,2})\.\s+", value)
        # parts: [prefix, num, rest, num, rest, ...]
        for i in range(1, len(parts), 2):
            rest = (parts[i + 1] if i + 1 < len(parts) else "").strip()
            if not rest:
                continue
            candidate = rest.split("\n", 1)[0].strip()
            candidate = candidate[:160].strip()
            if len(candidate) < 10:
                continue
            if _looks_like_attendance_or_access_info(candidate):
                continue
            titles.append(candidate)
            if len(titles) >= max_titles:
                break

    return _dedupe_titles_preserve_order(titles)[:max_titles]

_SessionLocal = None


def SessionLocal():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=db_connect())
    return _SessionLocal()


def _summary_doc_kind_subquery(db):
    first_document = (
        db.query(
            Document.catalog_id.label("catalog_id"),
            func.min(Document.id).label("document_id"),
        )
        .group_by(Document.catalog_id)
        .subquery("first_document")
    )
    return (
        db.query(
            Document.catalog_id.label("catalog_id"),
            summary_doc_kind_sql_expr(Document.category).label("doc_kind"),
        )
        .join(
            first_document,
            and_(
                Document.catalog_id == first_document.c.catalog_id,
                Document.id == first_document.c.document_id,
            ),
        )
        .subquery("summary_doc_kind")
    )


def select_catalog_ids_for_summary_hydration(db, limit: int | None = None, city: str | None = None) -> list[int]:
    """
    Select catalogs eligible for batch summary hydration.

    Agenda catalogs are included only when structured agenda items already exist,
    which keeps the batch path aligned with the interactive summary contract.
    """
    doc_kind = _summary_doc_kind_subquery(db)
    agenda_items_exist = (
        db.query(AgendaItem.id)
        .filter(AgendaItem.catalog_id == Catalog.id)
        .exists()
    )
    query = (
        db.query(Catalog.id)
        .join(doc_kind, doc_kind.c.catalog_id == Catalog.id)
        .join(Document, Document.catalog_id == Catalog.id)
        .join(Event, Event.id == Document.event_id)
        .filter(
            Catalog.content.isnot(None),
            Catalog.content != "",
            or_(
                and_(
                    doc_kind.c.doc_kind != "agenda",
                    or_(
                        Catalog.summary.is_(None),
                        Catalog.summary_source_hash.is_(None),
                        Catalog.content_hash.is_(None),
                        Catalog.summary_source_hash != Catalog.content_hash,
                    ),
                ),
                and_(
                    doc_kind.c.doc_kind == "agenda",
                    agenda_items_exist,
                    or_(
                        Catalog.summary.is_(None),
                        Catalog.summary_source_hash.is_(None),
                        Catalog.agenda_items_hash.is_(None),
                        Catalog.summary_source_hash != Catalog.agenda_items_hash,
                    ),
                ),
            ),
        )
        .order_by(Catalog.id)
    )
    query = apply_catalog_id_scope(query, Catalog.id)
    if city:
        query = query.filter(Event.source.in_(sorted(source_aliases_for_city(city))))
    if limit is not None:
        query = query.limit(limit)
    return [row[0] for row in query.distinct().all()]


def _summary_doc_kind_map(db, catalog_ids: list[int]) -> dict[int, str]:
    if not catalog_ids:
        return {}
    doc_kind = _summary_doc_kind_subquery(db)
    rows = (
        db.query(doc_kind.c.catalog_id, doc_kind.c.doc_kind)
        .filter(doc_kind.c.catalog_id.in_(catalog_ids))
        .all()
    )
    return {int(catalog_id): str(kind or "unknown") for catalog_id, kind in rows}


def _enqueue_embed_catalogs(catalog_ids: list[int]) -> dict[str, object]:
    deduped_ids = sorted({int(catalog_id) for catalog_id in catalog_ids if catalog_id is not None})
    failed_catalog_ids: list[int] = []
    enqueued = 0
    for catalog_id in deduped_ids:
        try:
            embed_catalog_task.delay(catalog_id)
            enqueued += 1
        except Exception as exc:
            logger.warning("embed_catalog_task.dispatch_failed catalog_id=%s error=%s", catalog_id, exc)
            failed_catalog_ids.append(catalog_id)
    return {
        "catalogs_considered": len(deduped_ids),
        "embed_enqueued": enqueued,
        "embed_dispatch_failed": len(failed_catalog_ids),
        "failed_catalog_ids": failed_catalog_ids,
    }


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
    """
    Generate summaries once across the current eligible backlog snapshot.
    """
    db = SessionLocal()
    try:
        catalog_ids = select_catalog_ids_for_summary_hydration(db, limit=limit, city=city)
    finally:
        db.close()

    counts = {
        "selected": len(catalog_ids),
        "complete": 0,
        "changed_catalogs": 0,
        "cached": 0,
        "stale": 0,
        "blocked_low_signal": 0,
        "blocked_ungrounded": 0,
        "not_generated_yet": 0,
        "error": 0,
        "other": 0,
        "agenda_deterministic_complete": 0,
        "llm_complete": 0,
        "deterministic_fallback_complete": 0,
        "reindexed": 0,
        "reindex_failed": 0,
        "embed_enqueued": 0,
        "embed_dispatch_failed": 0,
        AGENDA_SUMMARY_BUNDLE_BUILD_MS: 0,
        AGENDA_SUMMARY_RENDER_MS: 0,
        AGENDA_SUMMARY_PERSIST_MS: 0,
        AGENDA_SUMMARY_REINDEX_MS: 0,
        AGENDA_SUMMARY_EMBED_DISPATCH_MS: 0,
    }
    if not catalog_ids:
        logger.info("summary_hydration_backfill selected=0")
        if progress_callback:
            progress_callback(
                {
                    "event_type": "stage_finish",
                    "stage": "summary",
                    "counts": counts.copy(),
                    "detail": {"selected": 0},
                }
            )
        return counts

    if progress_callback:
        progress_callback(
            {
                "event_type": "stage_start",
                "stage": "summary",
                "counts": counts.copy(),
                "detail": {"selected": len(catalog_ids)},
            }
        )

    db = SessionLocal()
    try:
        doc_kind_by_catalog_id = _summary_doc_kind_map(db, catalog_ids)
    finally:
        db.close()

    agenda_catalog_ids = [catalog_id for catalog_id in catalog_ids if doc_kind_by_catalog_id.get(catalog_id) == "agenda"]
    agenda_results: dict[int, dict[str, Any]] = {}
    if agenda_catalog_ids:
        agenda_batch = build_deterministic_agenda_summary_payloads(
            agenda_catalog_ids,
            reindex_callback=reindex_catalogs,
            embed_callback=_enqueue_embed_catalogs,
        )
        agenda_results = dict(agenda_batch.get("results") or {})
        reindex_summary = agenda_batch.get("reindex_summary") or {}
        counts["reindexed"] += int(reindex_summary.get("catalogs_reindexed") or 0)
        counts["reindex_failed"] += int(reindex_summary.get("catalogs_failed") or 0)
        embed_summary = agenda_batch.get("embed_summary") or {}
        counts["embed_enqueued"] += int(embed_summary.get("embed_enqueued") or 0)
        counts["embed_dispatch_failed"] += int(embed_summary.get("embed_dispatch_failed") or 0)
        agenda_summary_timings = agenda_batch.get("agenda_summary_timings") or {}
        counts[AGENDA_SUMMARY_BUNDLE_BUILD_MS] += int(agenda_summary_timings.get(AGENDA_SUMMARY_BUNDLE_BUILD_MS) or 0)
        counts[AGENDA_SUMMARY_RENDER_MS] += int(agenda_summary_timings.get(AGENDA_SUMMARY_RENDER_MS) or 0)
        counts[AGENDA_SUMMARY_PERSIST_MS] += int(agenda_summary_timings.get(AGENDA_SUMMARY_PERSIST_MS) or 0)
        counts[AGENDA_SUMMARY_REINDEX_MS] += int(agenda_summary_timings.get(AGENDA_SUMMARY_REINDEX_MS) or 0)
        counts[AGENDA_SUMMARY_EMBED_DISPATCH_MS] += int(agenda_summary_timings.get(AGENDA_SUMMARY_EMBED_DISPATCH_MS) or 0)

    with summary_timeout_override(summary_timeout_seconds):
        for index, cid in enumerate(catalog_ids, start=1):
            if cid in agenda_results:
                result = agenda_results[cid]
            else:
                result = summarize_catalog_with_maintenance_mode(
                    cid,
                    summary_fallback_mode=summary_fallback_mode,
                    generate_summary_callable=lambda catalog_id: generate_summary_task.run(catalog_id, force=force),
                    deterministic_summary_callable=lambda catalog_id: build_deterministic_agenda_summary_payload(
                        catalog_id,
                        reindex_callback=reindex_catalog,
                        embed_callback=lambda target_catalog_id: embed_catalog_task.delay(target_catalog_id),
                    ),
                )

            status = str((result or {}).get("status") or "other")
            if status in counts:
                counts[status] += 1
            else:
                counts["other"] += 1
            counts["changed_catalogs"] += int(bool((result or {}).get("changed")))
            counts["reindexed"] += int((result or {}).get("reindexed") or 0)
            counts["reindex_failed"] += int((result or {}).get("reindex_failed") or 0)
            counts["embed_enqueued"] += int((result or {}).get("embed_enqueued") or 0)
            counts["embed_dispatch_failed"] += int((result or {}).get("embed_dispatch_failed") or 0)
            completion_mode = str((result or {}).get("completion_mode") or "")
            if completion_mode == "agenda_deterministic":
                counts["agenda_deterministic_complete"] += 1
            elif completion_mode == "llm":
                counts["llm_complete"] += 1
            elif completion_mode == "deterministic_fallback":
                counts["deterministic_fallback_complete"] += 1
            if progress_callback and (index == 1 or index % progress_every == 0 or index == len(catalog_ids)):
                progress_callback(
                    {
                        "event_type": "progress",
                        "stage": "summary",
                        "counts": counts.copy(),
                        "last_catalog_id": cid,
                        "detail": {
                            "done": index,
                            "total": len(catalog_ids),
                            "last_status": status,
                            "completion_mode": completion_mode,
                            "error": str((result or {}).get("error") or ""),
                        },
                    }
                )

    logger.info(
        "summary_hydration_backfill selected=%s complete=%s changed_catalogs=%s cached=%s stale=%s blocked_low_signal=%s blocked_ungrounded=%s not_generated_yet=%s error=%s other=%s agenda_deterministic_complete=%s llm_complete=%s deterministic_fallback_complete=%s reindexed=%s reindex_failed=%s embed_enqueued=%s embed_dispatch_failed=%s agenda_summary_bundle_build_ms=%s agenda_summary_render_ms=%s agenda_summary_persist_ms=%s agenda_summary_reindex_ms=%s agenda_summary_embed_dispatch_ms=%s",
        counts["selected"],
        counts["complete"],
        counts["changed_catalogs"],
        counts["cached"],
        counts["stale"],
        counts["blocked_low_signal"],
        counts["blocked_ungrounded"],
        counts["not_generated_yet"],
        counts["error"],
        counts["other"],
        counts["agenda_deterministic_complete"],
        counts["llm_complete"],
        counts["deterministic_fallback_complete"],
        counts["reindexed"],
        counts["reindex_failed"],
        counts["embed_enqueued"],
        counts["embed_dispatch_failed"],
        counts[AGENDA_SUMMARY_BUNDLE_BUILD_MS],
        counts[AGENDA_SUMMARY_RENDER_MS],
        counts[AGENDA_SUMMARY_PERSIST_MS],
        counts[AGENDA_SUMMARY_REINDEX_MS],
        counts[AGENDA_SUMMARY_EMBED_DISPATCH_MS],
    )
    if progress_callback:
        progress_callback({"event_type": "stage_finish", "stage": "summary", "counts": counts.copy()})
    return counts


def _get_celery_pool_from_argv(argv: list[str]) -> str | None:
    """
    Best-effort extraction of the Celery pool from argv.

    Why this exists:
    Celery's "sender" object passed to worker_ready isn't guaranteed to expose pool
    details across versions/configs, but argv is stable for our Docker entrypoint.
    """
    if not argv:
        return None
    for i, arg in enumerate(argv):
        if arg.startswith("--pool="):
            return arg.split("=", 1)[1].strip() or None
        if arg == "--pool" and (i + 1) < len(argv):
            return (argv[i + 1] or "").strip() or None
    return None


@worker_ready.connect
def _run_startup_purge_on_worker_ready(sender=None, **kwargs):
    # Guardrail: LocalAI's singleton is per-process. If a worker is configured with
    # concurrency > 1 (or a multiprocessing pool), each process will load its own model.
    # This can OOM a dev machine quickly.
    try:
        backend = (LOCAL_AI_BACKEND or "inprocess").strip().lower()
        concurrency = getattr(sender, "concurrency", None)
        if concurrency is None and sender is not None:
            concurrency = getattr(getattr(sender, "app", None), "conf", {}).get("worker_concurrency")  # type: ignore[attr-defined]
        try:
            if concurrency is not None:
                concurrency = int(concurrency)
        except Exception:
            concurrency = None
        pool = _get_celery_pool_from_argv(getattr(sender, "argv", None) or sys.argv)  # type: ignore[arg-type]

        guardrail_message = local_ai_runtime_guardrail_message(
            backend=backend,
            allow_multiprocess=LOCAL_AI_ALLOW_MULTIPROCESS,
            require_solo_pool=LOCAL_AI_REQUIRE_SOLO_POOL,
            concurrency=concurrency,
            pool=pool,
        )
        if guardrail_message:
            logger.critical(guardrail_message)
            raise SystemExit(1)
    except SystemExit:
        raise
    except Exception as guardrail_error:
        # Startup should stay resilient in non-worker contexts, but we log the check failure so
        # runtime misconfiguration never disappears silently.
        logger.warning("worker_ready.guardrail_check_failed error=%s", guardrail_error)

    # The purge is env-gated and DB-lock protected so concurrent starters are safe.
    result = run_startup_purge_if_enabled()
    logger.info(f"startup_purge_result={result}")

@app.task(bind=True, max_retries=3)
def generate_summary_task(self, catalog_id: int, force: bool = False):
    """
    Background task: generate and store a catalog summary.
    """
    db = SessionLocal()
    
    try:
        logger.info(f"Starting summarization for Catalog ID {catalog_id}")
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
        
        # Update DB
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

        changed = bool(persisted_summary["changed"])
        reindexed = 0
        reindex_failed = 0

        # Best-effort: update the search index for just this catalog so stale flags
        # and snippets stay in sync for future searches.
        try:
            reindex_catalog(catalog_id)
            reindexed = 1
        except Exception as reindex_error:
            reindex_failed = 1
            logger.warning("summary_generation.reindex_failed catalog_id=%s error=%s", catalog_id, reindex_error)
        
        # Fire-and-forget embedding update for semantic B2. We do not block summary success
        # on embedding failures; search can safely fall back to lexical until vectors hydrate.
        embed_enqueued = 0
        embed_dispatch_failed = 0
        try:
            embed_catalog_task.delay(catalog_id)
            embed_enqueued = 1
        except Exception as exc:
            logger.warning("embed_catalog_task.dispatch_failed catalog_id=%s error=%s", catalog_id, exc)
            embed_dispatch_failed = 1

        logger.info(f"Summarization complete for Catalog ID {catalog_id}")
        return {
            "status": "complete",
            "summary": summary,
            "changed": changed,
            "reindexed": reindexed,
            "reindex_failed": reindex_failed,
            "embed_enqueued": embed_enqueued,
            "embed_dispatch_failed": embed_dispatch_failed,
        }

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
            catalog.agenda_segmentation_status = "failed"
            catalog.agenda_segmentation_item_count = 0
            catalog.agenda_segmentation_attempted_at = datetime.now(timezone.utc)
            catalog.agenda_segmentation_error = classification.reason
            db.commit()
            return {"status": "error", "error": classification.reason}
        local_ai = LocalAI()
            
        resolved = resolve_agenda_items(db, catalog, doc, local_ai)
        items_data = resolved["items"]
        
        count = 0
        vote_extraction = {
            "status": "disabled",
            "processed_items": 0,
            "updated_items": 0,
            "skipped_items": 0,
            "failed_items": 0,
            "skip_reasons": {},
        }
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

            # Vote/outcome extraction is a separate post-segmentation stage.
            # Keep segmentation successful even if vote extraction later fails.
            if ENABLE_VOTE_EXTRACTION:
                try:
                    vote_counters = run_vote_extraction_for_catalog(
                        db,
                        local_ai,
                        catalog,
                        doc,
                        force=False,
                        agenda_items=created_items,
                    )
                    vote_extraction = {"status": "complete", **vote_counters}
                except Exception as vote_exc:
                    logger.warning(
                        "vote_extraction.post_segment_failed catalog_id=%s error=%s",
                        catalog_id,
                        vote_exc.__class__.__name__,
                    )
                    vote_extraction = {
                        "status": "failed",
                        "error": vote_exc.__class__.__name__,
                        "processed_items": 0,
                        "updated_items": 0,
                        "skipped_items": 0,
                        "failed_items": 0,
                        "skip_reasons": {},
                    }
            
            catalog.agenda_segmentation_status = "complete"
            catalog.agenda_segmentation_item_count = count
            catalog.agenda_segmentation_attempted_at = datetime.now(timezone.utc)
            catalog.agenda_segmentation_error = None
            db.commit()
            try:
                reindex_catalog(catalog_id)
            except Exception as reindex_error:
                # Agenda items are already persisted, so targeted reindex remains best-effort.
                logger.warning("agenda_segmentation.reindex_failed catalog_id=%s error=%s", catalog_id, reindex_error)
        else:
            # Terminal state: agenda segmentation ran but found no substantive items.
            catalog.agenda_segmentation_status = "empty"
            catalog.agenda_segmentation_item_count = 0
            catalog.agenda_segmentation_attempted_at = datetime.now(timezone.utc)
            catalog.agenda_segmentation_error = None
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

    except LocalAIConfigError as e:
        logger.critical(f"LocalAI misconfiguration: {e}")
        db.rollback()
        try:
            catalog = db.get(Catalog, catalog_id)
            if catalog:
                catalog.agenda_segmentation_status = "failed"
                catalog.agenda_segmentation_item_count = 0
                catalog.agenda_segmentation_attempted_at = datetime.now(timezone.utc)
                catalog.agenda_segmentation_error = str(e)[:500]
                db.commit()
        except Exception:
            db.rollback()
        return {"status": "error", "error": str(e)}
    except (SQLAlchemyError, RuntimeError, KeyError, ValueError) as e:
        logger.error(f"Task failed: {e}")
        db.rollback()
        # Best-effort: persist failure status so batch workers don't spin forever.
        try:
            catalog = db.get(Catalog, catalog_id)
            if catalog:
                catalog.agenda_segmentation_status = "failed"
                catalog.agenda_segmentation_item_count = 0
                catalog.agenda_segmentation_attempted_at = datetime.now(timezone.utc)
                catalog.agenda_segmentation_error = str(e)[:500]
                db.commit()
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
        catalog = db.get(Catalog, catalog_id)
        if not catalog:
            return {"error": "Catalog not found"}

        doc = db.query(Document).filter_by(catalog_id=catalog_id).first()
        if not doc:
            return {"error": "Document not linked to catalog"}

        if not ENABLE_VOTE_EXTRACTION and not force:
            return {
                "status": "disabled",
                "reason": "Vote extraction is disabled. Set ENABLE_VOTE_EXTRACTION=true or run with force=true.",
                "processed_items": 0,
                "updated_items": 0,
                "skipped_items": 0,
                "failed_items": 0,
                "skip_reasons": {},
            }

        existing_items = (
            db.query(AgendaItem)
            .filter_by(catalog_id=catalog_id)
            .order_by(AgendaItem.order)
            .all()
        )
        if not existing_items:
            return {
                "status": "not_generated_yet",
                "reason": "Vote extraction requires segmented agenda items. Run segmentation first.",
                "processed_items": 0,
                "updated_items": 0,
                "skipped_items": 0,
                "failed_items": 0,
                "skip_reasons": {},
            }

        counters = run_vote_extraction_for_catalog(
            db,
            local_ai,
            catalog,
            doc,
            force=force,
            agenda_items=existing_items,
        )
        db.commit()

        try:
            reindex_catalog(catalog_id)
        except Exception as reindex_error:
            # Summary persistence already succeeded, so targeted reindex remains best-effort.
            logger.warning("summary_generation.reindex_failed catalog_id=%s error=%s", catalog_id, reindex_error)

        return {"status": "complete", **counters}
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


@app.task(bind=True, max_retries=3)
def compute_lineage_task(self):
    """
    Recompute meeting-level lineage assignments from related_ids.
    """
    db = SessionLocal()
    lock_key = 90412031
    lock_acquired = False
    try:
        is_postgres = db.get_bind().dialect.name == "postgresql"
        if is_postgres:
            row = db.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": lock_key}).first()
            lock_acquired = bool(row and row[0])
            if not lock_acquired:
                return {"status": "skipped", "reason": "lineage_recompute_in_progress"}

        # Full recompute is intentional: one new bridge edge can merge multiple prior components.
        result = compute_lineage_assignments(
            db,
            min_edge_confidence=LINEAGE_MIN_EDGE_CONFIDENCE,
            require_mutual_edges=LINEAGE_REQUIRE_MUTUAL_EDGES,
        )
        db.commit()
        record_lineage_recompute(updated_count=result.updated_count, merge_count=result.merge_count)
        return {
            "status": "complete",
            "catalog_count": result.catalog_count,
            "component_count": result.component_count,
            "merge_count": result.merge_count,
            "updated_count": result.updated_count,
        }
    except (SQLAlchemyError, RuntimeError, ValueError) as e:
        db.rollback()
        logger.error("compute_lineage_task failed: %s", e)
        raise self.retry(exc=e, countdown=30)
    finally:
        if lock_acquired:
            try:
                db.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": lock_key})
                db.commit()
            except Exception:
                db.rollback()
        db.close()


@app.task(bind=True, max_retries=1)
def compute_lineage_for_catalog_task(self, catalog_id: int):
    """
    Catalog-triggered lineage update wrapper.
    """
    _ = catalog_id
    return compute_lineage_task.run(self)

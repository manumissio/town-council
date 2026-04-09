from __future__ import annotations

from typing import Any, Callable

from sqlalchemy import and_, func, or_

from pipeline.backlog_maintenance import (
    AGENDA_SUMMARY_BUNDLE_BUILD_MS,
    AGENDA_SUMMARY_EMBED_DISPATCH_MS,
    AGENDA_SUMMARY_PERSIST_MS,
    AGENDA_SUMMARY_REINDEX_MS,
    AGENDA_SUMMARY_RENDER_MS,
    build_deterministic_agenda_summary_payload,
    build_deterministic_agenda_summary_payloads,
    summarize_catalog_with_maintenance_mode,
    summary_timeout_override,
)
from pipeline.city_scope import source_aliases_for_city
from pipeline.document_kinds import summary_doc_kind_sql_expr
from pipeline.indexer import reindex_catalog, reindex_catalogs
from pipeline.models import AgendaItem, Catalog, Document, Event
from pipeline.profiling import apply_catalog_id_scope
from pipeline.semantic_tasks import embed_catalog_task
from pipeline.task_runtime import logger, task_session


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


def select_catalog_ids_for_summary_hydration(
    db,
    limit: int | None = None,
    city: str | None = None,
) -> list[int]:
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
        except Exception as exc:  # noqa: BLE001
            # Embed dispatch is best-effort here because summary writes are already durable.
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
    generate_summary_callable: Callable[[int], dict[str, Any]],
    session_factory: Callable[[], Any] = task_session,
    select_catalog_ids_callable: Callable[[Any, int | None, str | None], list[int]] = select_catalog_ids_for_summary_hydration,
    summary_doc_kind_map_callable: Callable[[Any, list[int]], dict[int, str]] = _summary_doc_kind_map,
    agenda_summary_batch_builder: Callable[..., dict[str, Any]] = build_deterministic_agenda_summary_payloads,
    summarize_catalog_callable: Callable[..., dict[str, Any]] = summarize_catalog_with_maintenance_mode,
) -> dict[str, int]:
    """
    Generate summaries once across the current eligible backlog snapshot.
    """
    db = session_factory()
    try:
        catalog_ids = select_catalog_ids_callable(db, limit, city)
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

    db = session_factory()
    try:
        doc_kind_by_catalog_id = summary_doc_kind_map_callable(db, catalog_ids)
    finally:
        db.close()

    agenda_catalog_ids = [catalog_id for catalog_id in catalog_ids if doc_kind_by_catalog_id.get(catalog_id) == "agenda"]
    agenda_results: dict[int, dict[str, Any]] = {}
    if agenda_catalog_ids:
        agenda_batch = agenda_summary_batch_builder(
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
                result = summarize_catalog_callable(
                    cid,
                    summary_fallback_mode=summary_fallback_mode,
                    generate_summary_callable=lambda catalog_id: generate_summary_callable(catalog_id),
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

from __future__ import annotations

from collections import defaultdict
from time import perf_counter
from typing import Any, Callable

from pipeline import llm as llm_mod
from pipeline.agenda_summary_callbacks import empty_callback_summary, time_embed_callback, time_reindex_callback
from pipeline.agenda_summary_contracts import (
    AGENDA_SUMMARY_BUNDLE_BUILD_MS,
    AGENDA_SUMMARY_CATALOG_NOT_FOUND_ERROR,
    AGENDA_SUMMARY_PERSIST_MS,
    AGENDA_SUMMARY_READY_STATUS,
    AGENDA_SUMMARY_RENDER_MS,
    AgendaSummaryPayload,
    elapsed_millis,
    empty_agenda_summary_timings,
    rounded_agenda_summary_timings,
)
from pipeline.agenda_summary_inputs import build_agenda_summary_input_bundle
from pipeline.config import AGENDA_SUMMARY_MAX_INPUT_CHARS, AGENDA_SUMMARY_MIN_RESERVED_OUTPUT_CHARS
from pipeline.db_session import db_session
from pipeline.laserfiche_error_pages import classify_catalog_bad_content
from pipeline.models import AgendaItem, Catalog, Document
from pipeline.summary_freshness import compute_summary_source_hash


def build_deterministic_agenda_summary_payload(
    catalog_id: int,
    *,
    reindex_callback: Callable[[int], Any] | None = None,
    embed_callback: Callable[[int], Any] | None = None,
    build_payloads_callable: Callable[..., AgendaSummaryPayload] | None = None,
) -> AgendaSummaryPayload:
    batch_builder = build_payloads_callable or build_deterministic_agenda_summary_payloads
    batch = batch_builder(
        [catalog_id],
        reindex_callback=(
            (lambda catalog_ids: reindex_callback(catalog_id)) if reindex_callback is not None else None
        ),
        embed_callback=(
            (lambda catalog_ids: embed_callback(catalog_id)) if embed_callback is not None else None
        ),
    )
    return batch["results"].get(
        catalog_id,
        {"status": "error", "error": AGENDA_SUMMARY_CATALOG_NOT_FOUND_ERROR},
    )


def build_deterministic_agenda_summary_payloads(
    catalog_ids: list[int],
    *,
    reindex_callback: Callable[[list[int]], Any] | None = None,
    embed_callback: Callable[[list[int]], Any] | None = None,
    max_input_chars: int = AGENDA_SUMMARY_MAX_INPUT_CHARS,
    min_reserved_output_chars: int = AGENDA_SUMMARY_MIN_RESERVED_OUTPUT_CHARS,
    session_factory: Callable[[], Any] = db_session,
) -> AgendaSummaryPayload:
    ordered_catalog_ids = [int(catalog_id) for catalog_id in catalog_ids]
    if not ordered_catalog_ids:
        return _empty_batch_payload()

    agenda_summary_timings = empty_agenda_summary_timings()
    with session_factory() as session:
        catalogs, documents_by_catalog_id, agenda_items_by_catalog_id = _load_agenda_summary_records(
            session,
            ordered_catalog_ids,
        )
        results, changed_catalog_ids = _build_batch_results(
            ordered_catalog_ids,
            catalogs,
            documents_by_catalog_id,
            agenda_items_by_catalog_id,
            agenda_summary_timings,
            max_input_chars=max_input_chars,
            min_reserved_output_chars=min_reserved_output_chars,
        )
        commit_started_at = perf_counter()
        session.commit()
        agenda_summary_timings[AGENDA_SUMMARY_PERSIST_MS] += elapsed_millis(commit_started_at)

    return {
        "results": results,
        "changed_catalog_ids": changed_catalog_ids,
        "reindex_summary": time_reindex_callback(agenda_summary_timings, changed_catalog_ids, reindex_callback),
        "embed_summary": time_embed_callback(agenda_summary_timings, changed_catalog_ids, embed_callback),
        "agenda_summary_timings": rounded_agenda_summary_timings(agenda_summary_timings),
    }


def persist_agenda_summary(
    *,
    catalog: Catalog,
    summary: str,
    content_hash: str | None,
    agenda_items_hash: str | None,
) -> AgendaSummaryPayload:
    prior_summary = catalog.summary
    prior_summary_source_hash = catalog.summary_source_hash
    prior_agenda_items_hash = catalog.agenda_items_hash
    summary_source_hash = compute_summary_source_hash(
        "agenda",
        content_hash=content_hash,
        agenda_items_hash=agenda_items_hash,
    )
    catalog.summary = summary
    if content_hash:
        catalog.content_hash = content_hash
    catalog.agenda_items_hash = agenda_items_hash
    if summary_source_hash:
        catalog.summary_source_hash = summary_source_hash

    changed = bool(
        prior_summary != summary
        or prior_summary_source_hash != summary_source_hash
        or prior_agenda_items_hash != agenda_items_hash
    )
    return {"status": "complete", "summary": summary, "changed": changed}


def _empty_batch_payload() -> AgendaSummaryPayload:
    return {
        "results": {},
        "changed_catalog_ids": [],
        "reindex_summary": empty_callback_summary(
            catalogs_considered_key="catalogs_considered",
            success_key="catalogs_reindexed",
            failure_key="catalogs_failed",
        ),
        "embed_summary": empty_callback_summary(
            catalogs_considered_key="catalogs_considered",
            success_key="embed_enqueued",
            failure_key="embed_dispatch_failed",
        ),
        "agenda_summary_timings": rounded_agenda_summary_timings(empty_agenda_summary_timings()),
    }


def _load_agenda_summary_records(
    session: Any,
    ordered_catalog_ids: list[int],
) -> tuple[dict[int, Catalog], dict[int, Document], dict[int, list[AgendaItem]]]:
    catalogs = {
        catalog.id: catalog
        for catalog in session.query(Catalog).filter(Catalog.id.in_(ordered_catalog_ids)).all()
    }
    documents_by_catalog_id: dict[int, Document] = {}
    for document in (
        session.query(Document)
        .filter(Document.catalog_id.in_(ordered_catalog_ids))
        .order_by(Document.catalog_id, Document.id)
        .all()
    ):
        documents_by_catalog_id.setdefault(document.catalog_id, document)

    agenda_items_by_catalog_id: dict[int, list[AgendaItem]] = defaultdict(list)
    for agenda_item in (
        session.query(AgendaItem)
        .filter(AgendaItem.catalog_id.in_(ordered_catalog_ids))
        .order_by(AgendaItem.catalog_id, AgendaItem.order)
        .all()
    ):
        agenda_items_by_catalog_id[agenda_item.catalog_id].append(agenda_item)
    return catalogs, documents_by_catalog_id, agenda_items_by_catalog_id


def _build_batch_results(
    ordered_catalog_ids: list[int],
    catalogs: dict[int, Catalog],
    documents_by_catalog_id: dict[int, Document],
    agenda_items_by_catalog_id: dict[int, list[AgendaItem]],
    agenda_summary_timings: dict[str, float],
    *,
    max_input_chars: int,
    min_reserved_output_chars: int,
) -> tuple[dict[int, AgendaSummaryPayload], list[int]]:
    results: dict[int, AgendaSummaryPayload] = {}
    changed_catalog_ids: list[int] = []
    for catalog_id in ordered_catalog_ids:
        catalog = catalogs.get(catalog_id)
        if not catalog:
            results[catalog_id] = {"status": "error", "error": AGENDA_SUMMARY_CATALOG_NOT_FOUND_ERROR}
            continue
        result = _build_catalog_result(
            catalog_id,
            catalog,
            documents_by_catalog_id,
            agenda_items_by_catalog_id,
            agenda_summary_timings,
            max_input_chars=max_input_chars,
            min_reserved_output_chars=min_reserved_output_chars,
        )
        if result.get("changed"):
            changed_catalog_ids.append(catalog_id)
        results[catalog_id] = result
    return results, changed_catalog_ids


def _build_catalog_result(
    catalog_id: int,
    catalog: Catalog,
    documents_by_catalog_id: dict[int, Document],
    agenda_items_by_catalog_id: dict[int, list[AgendaItem]],
    agenda_summary_timings: dict[str, float],
    *,
    max_input_chars: int,
    min_reserved_output_chars: int,
) -> AgendaSummaryPayload:
    classification = classify_catalog_bad_content(catalog)
    if classification:
        return {"status": "error", "error": classification.reason}

    summary_bundle = _time_agenda_summary_bundle_build(
        agenda_summary_timings,
        catalog=catalog,
        document=documents_by_catalog_id.get(catalog_id),
        agenda_items=agenda_items_by_catalog_id.get(catalog_id, []),
        max_input_chars=max_input_chars,
        min_reserved_output_chars=min_reserved_output_chars,
    )
    if summary_bundle.get("status") != AGENDA_SUMMARY_READY_STATUS:
        return summary_bundle

    summary_result = _time_agenda_summary_render(agenda_summary_timings, summary_bundle)
    persist_started_at = perf_counter()
    persisted_result = persist_agenda_summary(
        catalog=catalog,
        summary=str(summary_result.get("summary") or ""),
        content_hash=summary_bundle["content_hash"],
        agenda_items_hash=summary_bundle["agenda_items_hash"],
    )
    agenda_summary_timings[AGENDA_SUMMARY_PERSIST_MS] += elapsed_millis(persist_started_at)
    return {**persisted_result, "completion_mode": "agenda_deterministic"}


def _time_agenda_summary_bundle_build(
    agenda_summary_timings: dict[str, float],
    *,
    catalog: Catalog | None,
    document: Document | None,
    agenda_items: list[AgendaItem],
    max_input_chars: int,
    min_reserved_output_chars: int,
) -> AgendaSummaryPayload:
    started_at = perf_counter()
    summary_bundle = build_agenda_summary_input_bundle(
        catalog=catalog,
        document=document,
        agenda_items=agenda_items,
        max_input_chars=max_input_chars,
        min_reserved_output_chars=min_reserved_output_chars,
    )
    agenda_summary_timings[AGENDA_SUMMARY_BUNDLE_BUILD_MS] += elapsed_millis(started_at)
    return summary_bundle


def _time_agenda_summary_render(
    agenda_summary_timings: dict[str, float],
    summary_bundle: AgendaSummaryPayload,
) -> AgendaSummaryPayload:
    started_at = perf_counter()
    summary = llm_mod._deterministic_agenda_items_summary(
        summary_bundle["summary_items"],
        truncation_meta=summary_bundle["truncation_meta"],
    )
    agenda_summary_timings[AGENDA_SUMMARY_RENDER_MS] += elapsed_millis(started_at)
    return {"status": "complete", "summary": summary}

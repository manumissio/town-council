from __future__ import annotations

from time import perf_counter

from pipeline import indexer
from pipeline.agenda_summary_contracts import (
    AGENDA_SUMMARY_EMBED_DISPATCH_ERRORS,
    AGENDA_SUMMARY_EMBED_DISPATCH_MS,
    AGENDA_SUMMARY_REINDEX_ERRORS,
    AGENDA_SUMMARY_REINDEX_MS,
    AgendaSummaryPayload,
    elapsed_millis,
)
from pipeline.summary_backfill_dispatch import enqueue_embed_catalogs


def empty_side_effect_summary(
    *,
    catalogs_considered_key: str,
    success_key: str,
    failure_key: str,
) -> AgendaSummaryPayload:
    return {
        catalogs_considered_key: 0,
        success_key: 0,
        failure_key: 0,
        "failed_catalog_ids": [],
    }


def run_agenda_summary_reindex(
    agenda_summary_timings: dict[str, float],
    changed_catalog_ids: list[int],
) -> AgendaSummaryPayload:
    reindex_summary = empty_side_effect_summary(
        catalogs_considered_key="catalogs_considered",
        success_key="catalogs_reindexed",
        failure_key="catalogs_failed",
    )
    if not changed_catalog_ids:
        return reindex_summary

    started_at = perf_counter()
    try:
        payload = indexer.reindex_catalogs(changed_catalog_ids)
        reindex_summary = _normalize_side_effect_summary(
            payload,
            changed_catalog_ids,
            success_key="catalogs_reindexed",
            failure_key="catalogs_failed",
        )
    except AGENDA_SUMMARY_REINDEX_ERRORS as error:
        # Summary writes are already durable, so maintenance reports this failure.
        reindex_summary = _failed_side_effect_summary(
            changed_catalog_ids,
            failure_key="catalogs_failed",
            success_key="catalogs_reindexed",
            error=error,
        )
    finally:
        agenda_summary_timings[AGENDA_SUMMARY_REINDEX_MS] += elapsed_millis(started_at)
    return reindex_summary


def run_agenda_summary_embed_dispatch(
    agenda_summary_timings: dict[str, float],
    changed_catalog_ids: list[int],
) -> AgendaSummaryPayload:
    embed_summary = empty_side_effect_summary(
        catalogs_considered_key="catalogs_considered",
        success_key="embed_enqueued",
        failure_key="embed_dispatch_failed",
    )
    if not changed_catalog_ids:
        return embed_summary

    started_at = perf_counter()
    try:
        payload = enqueue_embed_catalogs(changed_catalog_ids)
        embed_summary = _normalize_side_effect_summary(
            payload,
            changed_catalog_ids,
            success_key="embed_enqueued",
            failure_key="embed_dispatch_failed",
        )
    except AGENDA_SUMMARY_EMBED_DISPATCH_ERRORS as error:
        # Embedding is post-commit and must not downgrade summary durability.
        embed_summary = _failed_side_effect_summary(
            changed_catalog_ids,
            failure_key="embed_dispatch_failed",
            success_key="embed_enqueued",
            error=error,
        )
    finally:
        agenda_summary_timings[AGENDA_SUMMARY_EMBED_DISPATCH_MS] += elapsed_millis(started_at)
    return embed_summary


def _normalize_side_effect_summary(
    payload: dict[str, object],
    changed_catalog_ids: list[int],
    *,
    success_key: str,
    failure_key: str,
) -> AgendaSummaryPayload:
    return {
        "catalogs_considered": int(
            payload.get("catalogs_considered") or len(changed_catalog_ids)
        ),
        success_key: int(payload.get(success_key) or 0),
        failure_key: int(payload.get(failure_key) or 0),
        "failed_catalog_ids": list(payload.get("failed_catalog_ids") or []),
    }


def _failed_side_effect_summary(
    changed_catalog_ids: list[int],
    *,
    failure_key: str,
    success_key: str,
    error: BaseException,
) -> AgendaSummaryPayload:
    return {
        "catalogs_considered": len(changed_catalog_ids),
        success_key: 0,
        failure_key: len(changed_catalog_ids),
        "failed_catalog_ids": list(changed_catalog_ids),
        "error": str(error),
    }

from __future__ import annotations

from time import perf_counter
from typing import Any, Callable

from pipeline.agenda_summary_contracts import (
    AGENDA_SUMMARY_EMBED_DISPATCH_ERRORS,
    AGENDA_SUMMARY_EMBED_DISPATCH_MS,
    AGENDA_SUMMARY_REINDEX_ERRORS,
    AGENDA_SUMMARY_REINDEX_MS,
    AgendaSummaryPayload,
    elapsed_millis,
)


def empty_callback_summary(
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


def time_reindex_callback(
    agenda_summary_timings: dict[str, float],
    changed_catalog_ids: list[int],
    reindex_callback: Callable[[list[int]], Any] | None,
) -> AgendaSummaryPayload:
    reindex_summary = empty_callback_summary(
        catalogs_considered_key="catalogs_considered",
        success_key="catalogs_reindexed",
        failure_key="catalogs_failed",
    )
    if not changed_catalog_ids or reindex_callback is None:
        return reindex_summary

    started_at = perf_counter()
    try:
        payload = reindex_callback(changed_catalog_ids)
        if isinstance(payload, dict):
            reindex_summary = {
                "catalogs_considered": int(payload.get("catalogs_considered") or len(changed_catalog_ids)),
                "catalogs_reindexed": int(payload.get("catalogs_reindexed") or 0),
                "catalogs_failed": int(payload.get("catalogs_failed") or 0),
                "failed_catalog_ids": list(payload.get("failed_catalog_ids") or []),
            }
    except AGENDA_SUMMARY_REINDEX_ERRORS as error:
        # Summary write already committed; report maintenance failure without rollback.
        reindex_summary = _failed_callback_summary(
            changed_catalog_ids,
            failure_key="catalogs_failed",
            success_key="catalogs_reindexed",
            error=error,
        )
    finally:
        agenda_summary_timings[AGENDA_SUMMARY_REINDEX_MS] += elapsed_millis(started_at)
    return reindex_summary


def time_embed_callback(
    agenda_summary_timings: dict[str, float],
    changed_catalog_ids: list[int],
    embed_callback: Callable[[list[int]], Any] | None,
) -> AgendaSummaryPayload:
    embed_summary = empty_callback_summary(
        catalogs_considered_key="catalogs_considered",
        success_key="embed_enqueued",
        failure_key="embed_dispatch_failed",
    )
    if not changed_catalog_ids or embed_callback is None:
        return embed_summary

    started_at = perf_counter()
    try:
        payload = embed_callback(changed_catalog_ids)
        if isinstance(payload, dict):
            embed_summary = {
                "catalogs_considered": int(payload.get("catalogs_considered") or len(changed_catalog_ids)),
                "embed_enqueued": int(payload.get("embed_enqueued") or 0),
                "embed_dispatch_failed": int(payload.get("embed_dispatch_failed") or 0),
                "failed_catalog_ids": list(payload.get("failed_catalog_ids") or []),
            }
    except AGENDA_SUMMARY_EMBED_DISPATCH_ERRORS as error:
        # Embedding is post-commit; failed dispatch should not downgrade summary durability.
        embed_summary = _failed_callback_summary(
            changed_catalog_ids,
            failure_key="embed_dispatch_failed",
            success_key="embed_enqueued",
            error=error,
        )
    finally:
        agenda_summary_timings[AGENDA_SUMMARY_EMBED_DISPATCH_MS] += elapsed_millis(started_at)
    return embed_summary


def _failed_callback_summary(
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

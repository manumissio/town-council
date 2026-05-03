from __future__ import annotations

from time import perf_counter
from typing import Any

from celery.exceptions import CeleryError
from kombu.exceptions import KombuError
from meilisearch.errors import MeilisearchError
from sqlalchemy.exc import SQLAlchemyError

# Any is required here because maintenance payloads mix ORM objects,
# callback summaries, and JSON-compatible API/task payload values.
AgendaSummaryPayload = dict[str, Any]

AGENDA_SUMMARY_READY_STATUS = "ready"
AGENDA_SUMMARY_SEGMENTATION_REQUIRED_REASON = (
    "Agenda summary requires segmented agenda items. Run segmentation first."
)
AGENDA_SUMMARY_BLOCKED_LOW_SIGNAL_REASON = (
    "No substantive agenda items detected after boilerplate filtering. Re-segment the agenda."
)
AGENDA_SUMMARY_CATALOG_NOT_FOUND_ERROR = "Catalog not found"
AGENDA_SUMMARY_DOCUMENT_NOT_FOUND_ERROR = "Document not found"
AGENDA_SUMMARY_BUNDLE_BUILD_MS = "agenda_summary_bundle_build_ms"
AGENDA_SUMMARY_RENDER_MS = "agenda_summary_render_ms"
AGENDA_SUMMARY_PERSIST_MS = "agenda_summary_persist_ms"
AGENDA_SUMMARY_REINDEX_MS = "agenda_summary_reindex_ms"
AGENDA_SUMMARY_EMBED_DISPATCH_MS = "agenda_summary_embed_dispatch_ms"
AGENDA_SUMMARY_TIMING_KEYS = (
    AGENDA_SUMMARY_BUNDLE_BUILD_MS,
    AGENDA_SUMMARY_RENDER_MS,
    AGENDA_SUMMARY_PERSIST_MS,
    AGENDA_SUMMARY_REINDEX_MS,
    AGENDA_SUMMARY_EMBED_DISPATCH_MS,
)
AGENDA_SUMMARY_REINDEX_ERRORS = (
    MeilisearchError,
    SQLAlchemyError,
    RuntimeError,
    TypeError,
    ValueError,
    KeyError,
)
AGENDA_SUMMARY_EMBED_DISPATCH_ERRORS = (
    CeleryError,
    KombuError,
    RuntimeError,
    TypeError,
    ValueError,
    KeyError,
)
AGENDA_SUMMARY_CALLABLE_ERRORS = (RuntimeError, TypeError, ValueError, KeyError)


def empty_agenda_summary_timings() -> dict[str, float]:
    return {metric_name: 0 for metric_name in AGENDA_SUMMARY_TIMING_KEYS}


def elapsed_millis(started_at: float) -> float:
    return (perf_counter() - started_at) * 1000.0


def rounded_agenda_summary_timings(agenda_summary_timings: dict[str, float]) -> dict[str, int]:
    return {
        metric_name: int(round(agenda_summary_timings.get(metric_name, 0.0)))
        for metric_name in AGENDA_SUMMARY_TIMING_KEYS
    }

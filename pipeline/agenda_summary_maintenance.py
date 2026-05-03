from __future__ import annotations

from typing import Any, Callable

from pipeline.agenda_summary_batch import (
    build_deterministic_agenda_summary_payload as _build_deterministic_agenda_summary_payload,
)
from pipeline.agenda_summary_batch import (
    build_deterministic_agenda_summary_payloads,
    persist_agenda_summary,
)
from pipeline.agenda_summary_contracts import (
    AGENDA_SUMMARY_BLOCKED_LOW_SIGNAL_REASON,
    AGENDA_SUMMARY_BUNDLE_BUILD_MS,
    AGENDA_SUMMARY_CALLABLE_ERRORS,
    AGENDA_SUMMARY_CATALOG_NOT_FOUND_ERROR,
    AGENDA_SUMMARY_DOCUMENT_NOT_FOUND_ERROR,
    AGENDA_SUMMARY_EMBED_DISPATCH_ERRORS,
    AGENDA_SUMMARY_EMBED_DISPATCH_MS,
    AGENDA_SUMMARY_PERSIST_MS,
    AGENDA_SUMMARY_READY_STATUS,
    AGENDA_SUMMARY_REINDEX_ERRORS,
    AGENDA_SUMMARY_REINDEX_MS,
    AGENDA_SUMMARY_RENDER_MS,
    AGENDA_SUMMARY_SEGMENTATION_REQUIRED_REASON,
    AGENDA_SUMMARY_TIMING_KEYS,
    AgendaSummaryPayload,
)
from pipeline.agenda_summary_fallback import (
    summarize_catalog_with_maintenance_mode as _summarize_catalog_with_maintenance_mode,
)
from pipeline.agenda_summary_fallback import (
    summarize_catalog_with_optional_fallback as _summarize_catalog_with_optional_fallback,
)
from pipeline.agenda_summary_inputs import build_agenda_summary_input_bundle
from pipeline.document_kinds import normalize_summary_doc_kind

__all__ = [
    "AGENDA_SUMMARY_BLOCKED_LOW_SIGNAL_REASON",
    "AGENDA_SUMMARY_BUNDLE_BUILD_MS",
    "AGENDA_SUMMARY_CALLABLE_ERRORS",
    "AGENDA_SUMMARY_CATALOG_NOT_FOUND_ERROR",
    "AGENDA_SUMMARY_DOCUMENT_NOT_FOUND_ERROR",
    "AGENDA_SUMMARY_EMBED_DISPATCH_ERRORS",
    "AGENDA_SUMMARY_EMBED_DISPATCH_MS",
    "AGENDA_SUMMARY_PERSIST_MS",
    "AGENDA_SUMMARY_READY_STATUS",
    "AGENDA_SUMMARY_REINDEX_ERRORS",
    "AGENDA_SUMMARY_REINDEX_MS",
    "AGENDA_SUMMARY_RENDER_MS",
    "AGENDA_SUMMARY_SEGMENTATION_REQUIRED_REASON",
    "AGENDA_SUMMARY_TIMING_KEYS",
    "AgendaSummaryPayload",
    "build_agenda_summary_input_bundle",
    "build_deterministic_agenda_summary_payload",
    "build_deterministic_agenda_summary_payloads",
    "normalize_summary_doc_kind",
    "persist_agenda_summary",
    "summarize_catalog_with_maintenance_mode",
    "summarize_catalog_with_optional_fallback",
]


def build_deterministic_agenda_summary_payload(
    catalog_id: int,
    *,
    reindex_callback: Callable[[int], Any] | None = None,
    embed_callback: Callable[[int], Any] | None = None,
    build_payloads_callable: Callable[..., AgendaSummaryPayload] | None = None,
) -> AgendaSummaryPayload:
    return _build_deterministic_agenda_summary_payload(
        catalog_id,
        reindex_callback=reindex_callback,
        embed_callback=embed_callback,
        build_payloads_callable=build_payloads_callable or build_deterministic_agenda_summary_payloads,
    )


def summarize_catalog_with_optional_fallback(
    catalog_id: int,
    *,
    summary_fallback_mode: str = "none",
    generate_summary_callable: Callable[[int], dict[str, Any] | None],
    deterministic_summary_callable: Callable[[int], dict[str, Any]],
    capture_summary_fallback_events_factory: Callable[[], Any] | None = None,
) -> AgendaSummaryPayload:
    return _summarize_catalog_with_optional_fallback(
        catalog_id,
        summary_fallback_mode=summary_fallback_mode,
        generate_summary_callable=generate_summary_callable,
        deterministic_summary_callable=deterministic_summary_callable,
        capture_summary_fallback_events_factory=capture_summary_fallback_events_factory,
    )


def summarize_catalog_with_maintenance_mode(
    catalog_id: int,
    *,
    summary_fallback_mode: str = "none",
    generate_summary_callable: Callable[[int], dict[str, Any] | None],
    deterministic_summary_callable: Callable[[int], dict[str, Any]],
    session_factory: Callable[[], Any] | None = None,
    capture_summary_fallback_events_factory: Callable[[], Any] | None = None,
) -> AgendaSummaryPayload:
    kwargs: dict[str, Any] = {}
    if session_factory is not None:
        kwargs["session_factory"] = session_factory
    return _summarize_catalog_with_maintenance_mode(
        catalog_id,
        summary_fallback_mode=summary_fallback_mode,
        generate_summary_callable=generate_summary_callable,
        deterministic_summary_callable=deterministic_summary_callable,
        capture_summary_fallback_events_factory=capture_summary_fallback_events_factory,
        optional_fallback_callable=summarize_catalog_with_optional_fallback,
        **kwargs,
    )

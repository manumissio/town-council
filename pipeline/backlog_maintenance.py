from __future__ import annotations

from typing import Any, Callable

from pipeline import llm as llm_mod  # noqa: F401
from pipeline import agenda_segmentation_maintenance as agenda_segmentation_maintenance_mod
from pipeline import agenda_summary_maintenance as agenda_summary_maintenance_mod
from pipeline.agenda_resolver import has_viable_structured_agenda_source
from pipeline.config import AGENDA_SUMMARY_MAX_INPUT_CHARS, AGENDA_SUMMARY_MIN_RESERVED_OUTPUT_CHARS
from pipeline.db_session import db_session
from pipeline.models import Document

AGENDA_SUMMARY_READY_STATUS = agenda_summary_maintenance_mod.AGENDA_SUMMARY_READY_STATUS
AGENDA_SUMMARY_SEGMENTATION_REQUIRED_REASON = (
    agenda_summary_maintenance_mod.AGENDA_SUMMARY_SEGMENTATION_REQUIRED_REASON
)
AGENDA_SUMMARY_BLOCKED_LOW_SIGNAL_REASON = (
    agenda_summary_maintenance_mod.AGENDA_SUMMARY_BLOCKED_LOW_SIGNAL_REASON
)
AGENDA_SUMMARY_CATALOG_NOT_FOUND_ERROR = agenda_summary_maintenance_mod.AGENDA_SUMMARY_CATALOG_NOT_FOUND_ERROR
AGENDA_SUMMARY_DOCUMENT_NOT_FOUND_ERROR = agenda_summary_maintenance_mod.AGENDA_SUMMARY_DOCUMENT_NOT_FOUND_ERROR
AGENDA_SUMMARY_BUNDLE_BUILD_MS = agenda_summary_maintenance_mod.AGENDA_SUMMARY_BUNDLE_BUILD_MS
AGENDA_SUMMARY_RENDER_MS = agenda_summary_maintenance_mod.AGENDA_SUMMARY_RENDER_MS
AGENDA_SUMMARY_PERSIST_MS = agenda_summary_maintenance_mod.AGENDA_SUMMARY_PERSIST_MS
AGENDA_SUMMARY_REINDEX_MS = agenda_summary_maintenance_mod.AGENDA_SUMMARY_REINDEX_MS
AGENDA_SUMMARY_EMBED_DISPATCH_MS = agenda_summary_maintenance_mod.AGENDA_SUMMARY_EMBED_DISPATCH_MS
AGENDA_SUMMARY_TIMING_KEYS = agenda_summary_maintenance_mod.AGENDA_SUMMARY_TIMING_KEYS

provider_timeout_override = agenda_segmentation_maintenance_mod.provider_timeout_override
segment_timeout_override = agenda_segmentation_maintenance_mod.segment_timeout_override
summary_timeout_override = agenda_segmentation_maintenance_mod.summary_timeout_override
capture_agenda_fallback_events = agenda_segmentation_maintenance_mod.capture_agenda_fallback_events
capture_summary_fallback_events = agenda_segmentation_maintenance_mod.capture_summary_fallback_events
looks_structured_enough_for_heuristic_segmentation = (
    agenda_segmentation_maintenance_mod.looks_structured_enough_for_heuristic_segmentation
)
HeuristicOnlyLocalAI = agenda_segmentation_maintenance_mod.HeuristicOnlyLocalAI
persist_segmented_agenda = agenda_segmentation_maintenance_mod.persist_segmented_agenda


def segment_catalog_with_mode(catalog_id: int, *, segment_mode: str = "normal") -> dict[str, Any]:
    return agenda_segmentation_maintenance_mod.segment_catalog_with_mode(
        catalog_id,
        segment_mode=segment_mode,
        session_factory=db_session,
        has_viable_structured_source=has_viable_structured_agenda_source,
    )


def build_agenda_summary_input_bundle(
    *,
    catalog,
    document,
    agenda_items,
    include_meeting_context: bool = False,
    max_input_chars: int | None = None,
    min_reserved_output_chars: int | None = None,
) -> dict[str, Any]:
    resolved_max_input_chars = (
        AGENDA_SUMMARY_MAX_INPUT_CHARS if max_input_chars is None else max_input_chars
    )
    resolved_min_reserved_output_chars = (
        AGENDA_SUMMARY_MIN_RESERVED_OUTPUT_CHARS
        if min_reserved_output_chars is None
        else min_reserved_output_chars
    )
    return agenda_summary_maintenance_mod.build_agenda_summary_input_bundle(
        catalog=catalog,
        document=document,
        agenda_items=agenda_items,
        include_meeting_context=include_meeting_context,
        max_input_chars=resolved_max_input_chars,
        min_reserved_output_chars=resolved_min_reserved_output_chars,
    )


def persist_agenda_summary(
    *,
    catalog,
    summary: str,
    content_hash: str | None,
    agenda_items_hash: str | None,
) -> dict[str, Any]:
    return agenda_summary_maintenance_mod.persist_agenda_summary(
        catalog=catalog,
        summary=summary,
        content_hash=content_hash,
        agenda_items_hash=agenda_items_hash,
    )


def build_deterministic_agenda_summary_payloads(
    catalog_ids: list[int],
    *,
    reindex_callback: Callable[[list[int]], Any] | None = None,
    embed_callback: Callable[[list[int]], Any] | None = None,
) -> dict[str, Any]:
    return agenda_summary_maintenance_mod.build_deterministic_agenda_summary_payloads(
        catalog_ids,
        reindex_callback=reindex_callback,
        embed_callback=embed_callback,
        max_input_chars=AGENDA_SUMMARY_MAX_INPUT_CHARS,
        min_reserved_output_chars=AGENDA_SUMMARY_MIN_RESERVED_OUTPUT_CHARS,
        session_factory=db_session,
    )


def build_deterministic_agenda_summary_payload(
    catalog_id: int,
    *,
    reindex_callback: Callable[[int], Any] | None = None,
    embed_callback: Callable[[int], Any] | None = None,
) -> dict[str, Any]:
    return agenda_summary_maintenance_mod.build_deterministic_agenda_summary_payload(
        catalog_id,
        reindex_callback=reindex_callback,
        embed_callback=embed_callback,
        build_payloads_callable=build_deterministic_agenda_summary_payloads,
    )


def summarize_catalog_with_optional_fallback(
    catalog_id: int,
    *,
    summary_fallback_mode: str = "none",
    generate_summary_callable: Callable[[int], dict[str, Any] | None],
    deterministic_summary_callable: Callable[[int], dict[str, Any]],
) -> dict[str, Any]:
    return agenda_summary_maintenance_mod.summarize_catalog_with_optional_fallback(
        catalog_id,
        summary_fallback_mode=summary_fallback_mode,
        generate_summary_callable=generate_summary_callable,
        deterministic_summary_callable=deterministic_summary_callable,
        capture_summary_fallback_events_factory=capture_summary_fallback_events,
    )


def summarize_catalog_with_maintenance_mode(
    catalog_id: int,
    *,
    summary_fallback_mode: str = "none",
    generate_summary_callable: Callable[[int], dict[str, Any] | None],
    deterministic_summary_callable: Callable[[int], dict[str, Any]],
) -> dict[str, Any]:
    """
    Maintenance hydration is allowed to skip agenda LLM summaries entirely.

    Why:
    Agenda backlog runs already have structured agenda items, and baseline profiling
    showed we were often paying for an LLM agenda summary only to replace it with the
    same deterministic agenda-items summary. Interactive one-off summary generation
    still uses the normal task path; this optimization is only for maintenance flows.
    """
    with db_session() as session:
        doc = session.query(Document).filter_by(catalog_id=catalog_id).first()
        doc_kind = agenda_summary_maintenance_mod.normalize_summary_doc_kind(
            doc.category if doc else "unknown"
        )

    if doc_kind == "agenda":
        return agenda_summary_maintenance_mod.summarize_catalog_with_maintenance_mode(
            catalog_id,
            summary_fallback_mode=summary_fallback_mode,
            generate_summary_callable=generate_summary_callable,
            deterministic_summary_callable=deterministic_summary_callable,
            session_factory=db_session,
            capture_summary_fallback_events_factory=capture_summary_fallback_events,
        )

    return summarize_catalog_with_optional_fallback(
        catalog_id,
        summary_fallback_mode=summary_fallback_mode,
        generate_summary_callable=generate_summary_callable,
        deterministic_summary_callable=deterministic_summary_callable,
    )

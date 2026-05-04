from __future__ import annotations

from pipeline.document_kinds import normalize_summary_doc_kind
from pipeline.summary_hydration_diagnostic_contracts import (
    AGENDA_DOC_KIND,
    AGENDA_SEGMENTATION_BLOCKED_ROOT_CAUSE,
    AGENDA_UNSCHEDULED_ROOT_CAUSE,
    BLOCKED_LOW_SIGNAL_PATH,
    ELIGIBLE_AGENDA_SUMMARY_PATH,
    ELIGIBLE_NON_AGENDA_SUMMARY_PATH,
    MISSING_CONTENT_PATH,
    MISSING_SUMMARY_ROOT_CAUSE_RATIO_THRESHOLD,
    NEEDS_SEGMENTATION_PATH,
    NON_AGENDA_UNSCHEDULED_ROOT_CAUSE,
    NO_DOMINANT_BACKLOG_ROOT_CAUSE,
    QUALITY_GATE_ROOT_CAUSE,
    SummaryHydrationSnapshot,
)
from pipeline.summary_quality import analyze_source_text, is_source_summarizable


def predict_summary_path(
    doc_kind: str | None,
    *,
    has_content: bool,
    has_agenda_items: bool,
    content: str | None,
) -> str:
    normalized_kind = normalize_summary_doc_kind(doc_kind)
    if not has_content:
        return MISSING_CONTENT_PATH
    if normalized_kind == AGENDA_DOC_KIND:
        if not has_agenda_items:
            return NEEDS_SEGMENTATION_PATH
        return ELIGIBLE_AGENDA_SUMMARY_PATH
    quality = analyze_source_text(content or "")
    if not is_source_summarizable(quality):
        return BLOCKED_LOW_SIGNAL_PATH
    return ELIGIBLE_NON_AGENDA_SUMMARY_PATH


def infer_primary_root_cause(snapshot: SummaryHydrationSnapshot) -> str:
    if (
        snapshot.agenda_missing_summary_without_items > 0
        and snapshot.agenda_missing_summary_without_items
        >= snapshot.missing_summary_total * MISSING_SUMMARY_ROOT_CAUSE_RATIO_THRESHOLD
    ):
        return AGENDA_SEGMENTATION_BLOCKED_ROOT_CAUSE
    if snapshot.non_agenda_summarizable > 0:
        return NON_AGENDA_UNSCHEDULED_ROOT_CAUSE
    if snapshot.non_agenda_blocked_low_signal > 0:
        return QUALITY_GATE_ROOT_CAUSE
    if snapshot.agenda_missing_summary_with_items > 0:
        return AGENDA_UNSCHEDULED_ROOT_CAUSE
    return NO_DOMINANT_BACKLOG_ROOT_CAUSE

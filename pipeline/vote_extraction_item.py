from __future__ import annotations

from datetime import datetime, timezone
import logging

from pipeline.vote_extraction_contracts import (
    LLM_EXTRACTED_VOTE_SOURCE,
    SKIP_REASON_ALREADY_HIGH_CONFIDENCE,
    SKIP_REASON_EXISTING_RESULT,
    SKIP_REASON_MISSING_TITLE,
    SKIP_REASON_TRUSTED_SOURCE,
    AgendaItemLike,
    CatalogLike,
    VoteExtractionCounters,
    VoteExtractionRuntimeHooks,
    VoteExtractionSettings,
    VoteExtractionResult,
)
from pipeline.vote_extraction_policy import (
    has_non_unknown_result,
    is_high_confidence_existing_llm_vote,
    is_trusted_existing_vote,
    result_text_from_label,
)


def empty_vote_counters() -> VoteExtractionCounters:
    return {
        "processed_items": 0,
        "updated_items": 0,
        "skipped_items": 0,
        "failed_items": 0,
        "skip_reasons": {},
    }


def count_processed_item(counters: VoteExtractionCounters) -> None:
    counters["processed_items"] += 1


def count_updated_item(counters: VoteExtractionCounters) -> None:
    counters["updated_items"] += 1


def count_skipped_item(counters: VoteExtractionCounters, reason: str) -> None:
    counters["skipped_items"] += 1
    counters["skip_reasons"][reason] = counters["skip_reasons"].get(reason, 0) + 1


def count_failed_item(counters: VoteExtractionCounters) -> None:
    counters["failed_items"] += 1


def skip_reason_before_extraction(
    item: AgendaItemLike,
    *,
    item_title: str,
    force: bool,
    settings: VoteExtractionSettings,
    runtime_hooks: VoteExtractionRuntimeHooks,
) -> str | None:
    if not item_title:
        return SKIP_REASON_MISSING_TITLE
    trusted_vote_checker = runtime_hooks.trusted_vote_checker or is_trusted_existing_vote
    high_confidence_vote_checker = runtime_hooks.high_confidence_vote_checker
    existing_result_checker = runtime_hooks.existing_result_checker or has_non_unknown_result
    if trusted_vote_checker(getattr(item, "votes", None)):
        return SKIP_REASON_TRUSTED_SOURCE
    if (
        not force
        and high_confidence_vote_checker is not None
        and high_confidence_vote_checker(getattr(item, "votes", None))
    ):
        return SKIP_REASON_ALREADY_HIGH_CONFIDENCE
    if (
        not force
        and high_confidence_vote_checker is None
        and is_high_confidence_existing_llm_vote(
            getattr(item, "votes", None),
            confidence_threshold=settings.confidence_threshold,
        )
    ):
        return SKIP_REASON_ALREADY_HIGH_CONFIDENCE
    if not force and existing_result_checker(getattr(item, "result", None)):
        return SKIP_REASON_EXISTING_RESULT
    return None


def build_vote_payload(extracted: VoteExtractionResult, *, extracted_at: datetime | None = None) -> dict[str, object]:
    timestamp = extracted_at or datetime.now(timezone.utc)
    return {
        "outcome_label": extracted.outcome_label,
        "motion_text": extracted.motion_text,
        "vote_tally_raw": extracted.vote_tally_raw,
        "yes_count": extracted.yes_count,
        "no_count": extracted.no_count,
        "abstain_count": extracted.abstain_count,
        "absent_count": extracted.absent_count,
        "confidence": extracted.confidence,
        "evidence_snippet": extracted.evidence_snippet,
        "source": LLM_EXTRACTED_VOTE_SOURCE,
        "extracted_at": timestamp.isoformat(),
    }


def update_item_vote(
    item: AgendaItemLike,
    extracted: VoteExtractionResult,
    *,
    logger: logging.Logger,
    catalog: CatalogLike,
    runtime_hooks: VoteExtractionRuntimeHooks,
) -> None:
    result_text_builder = runtime_hooks.result_text_builder or result_text_from_label
    item.result = result_text_builder(extracted.outcome_label)
    item.votes = build_vote_payload(extracted)
    logger.info(
        "vote_extraction.updated catalog_id=%s agenda_item_id=%s outcome=%s confidence=%.2f",
        catalog.id,
        getattr(item, "id", None),
        extracted.outcome_label,
        extracted.confidence,
    )


def log_extraction_failure(
    item: AgendaItemLike,
    *,
    catalog: CatalogLike,
    logger: logging.Logger,
    error: Exception,
) -> None:
    logger.warning(
        "vote_extraction.failed catalog_id=%s agenda_item_id=%s error=%s",
        catalog.id,
        getattr(item, "id", None),
        error.__class__.__name__,
    )

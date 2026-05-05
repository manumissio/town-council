from __future__ import annotations

import logging

from pipeline.vote_extraction_contracts import (
    LLM_EXTRACTED_VOTE_SOURCE,
    SKIP_REASON_LOW_CONFIDENCE,
    SKIP_REASON_UNKNOWN_NO_TALLY,
    TRUSTED_VOTE_SOURCES,
    UNKNOWN_RESULT_VALUES,
    VOTE_KEYWORDS,
    VoteExtractionSettings,
    VoteExtractionResult,
)


def result_text_from_label(outcome_label: str) -> str:
    mapping = {
        "passed": "Passed",
        "failed": "Failed",
        "deferred": "Deferred",
        "continued": "Continued",
        "tabled": "Tabled",
        "withdrawn": "Withdrawn",
        "no_action": "No Action",
        "unknown": "Unknown",
    }
    return mapping.get(outcome_label, "Unknown")


def is_high_confidence_existing_llm_vote(votes: object, *, confidence_threshold: float) -> bool:
    if not isinstance(votes, dict):
        return False
    source = str(votes.get("source") or "").strip().lower()
    confidence = votes.get("confidence", 0.0)
    try:
        confidence_value = float(confidence)
    except TypeError, ValueError:
        confidence_value = 0.0
    return source == LLM_EXTRACTED_VOTE_SOURCE and confidence_value >= confidence_threshold


def is_trusted_existing_vote(votes: object) -> bool:
    if not isinstance(votes, dict):
        return False
    source = str(votes.get("source") or "").strip().lower()
    return source in TRUSTED_VOTE_SOURCES


def has_non_unknown_result(result_value: object | None) -> bool:
    return str(result_value or "").strip().lower() not in UNKNOWN_RESULT_VALUES


def apply_ambiguity_penalty(
    result: VoteExtractionResult,
    item_text: str,
    *,
    confidence_threshold: float,
    logger: logging.Logger,
) -> VoteExtractionResult:
    text = (item_text or "").lower()
    has_vote_terms = any(keyword in text for keyword in VOTE_KEYWORDS)
    if has_vote_terms or result.outcome_label in {"unknown", "no_action"}:
        return result

    original_confidence = result.confidence
    result.confidence = max(0.0, result.confidence * 0.4)
    if result.confidence < confidence_threshold:
        logger.debug(
            "vote_extraction.ambiguity_penalty_below_threshold original_confidence=%s penalized_confidence=%s threshold=%s outcome_label=%s",
            original_confidence,
            result.confidence,
            confidence_threshold,
            result.outcome_label,
        )
    return result


def skip_reason_after_extraction(
    extracted: VoteExtractionResult,
    *,
    settings: VoteExtractionSettings,
) -> str | None:
    if extracted.confidence < settings.confidence_threshold:
        return SKIP_REASON_LOW_CONFIDENCE
    if extracted.outcome_label == "unknown" and all(
        value is None
        for value in (
            extracted.yes_count,
            extracted.no_count,
            extracted.abstain_count,
            extracted.absent_count,
        )
    ):
        return SKIP_REASON_UNKNOWN_NO_TALLY
    return None

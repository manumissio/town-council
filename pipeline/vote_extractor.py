from __future__ import annotations

import logging
from collections.abc import Sequence

from pipeline.config import (
    VOTE_EXTRACTION_CONFIDENCE_THRESHOLD,
    VOTE_EXTRACTION_CONTEXT_AFTER_CHARS,
    VOTE_EXTRACTION_CONTEXT_BEFORE_CHARS,
    VOTE_EXTRACTION_MAX_TOKENS,
    VOTE_EXTRACTION_MIN_TEXT_CHARS,
)
from pipeline.models import AgendaItem
from pipeline.vote_extraction_context import build_vote_context_text as _build_vote_context_text_impl
from pipeline.vote_extraction_contracts import (
    LLM_EXTRACTED_VOTE_SOURCE,
    OUTCOME_SYNONYMS,
    SKIP_REASON_ALREADY_HIGH_CONFIDENCE,
    SKIP_REASON_EXISTING_RESULT,
    SKIP_REASON_INSUFFICIENT_TEXT,
    SKIP_REASON_LOW_CONFIDENCE,
    SKIP_REASON_MISSING_TITLE,
    SKIP_REASON_TRUSTED_SOURCE,
    SKIP_REASON_UNKNOWN_NO_TALLY,
    TRUSTED_VOTE_SOURCES,
    UNKNOWN_RESULT_VALUES,
    VALID_OUTCOME_LABELS,
    VOTE_KEYWORDS,
    AgendaItemLike,
    AgendaItemQuery,
    AgendaItemSession,
    CatalogLike,
    DocumentLike,
    EventLike,
    VoteExtractionCounters,
    VoteExtractionModel,
    VoteExtractionResult,
    VoteExtractionRuntimeHooks,
    VoteExtractionSettings,
)
from pipeline.vote_extraction_parser import (
    coerce_optional_int as _coerce_optional_int_impl,
    extract_first_json_object as _extract_first_json_object_impl,
    normalize_outcome_label as _normalize_outcome_label_impl,
    parse_vote_extraction_response as _parse_vote_extraction_response_impl,
)
from pipeline.vote_extraction_policy import (
    apply_ambiguity_penalty as _apply_ambiguity_penalty_impl,
    has_non_unknown_result as _has_non_unknown_result_impl,
    is_high_confidence_existing_llm_vote as _is_high_confidence_existing_llm_vote_impl,
    is_trusted_existing_vote as _is_trusted_existing_vote_impl,
    result_text_from_label as _result_text_from_label_impl,
)
from pipeline.vote_extraction_prompting import prepare_vote_extraction_prompt as _prepare_vote_extraction_prompt_impl
from pipeline.vote_extraction_runner import (
    run_vote_extraction_for_catalog as _run_vote_extraction_for_catalog_impl,
)


logger = logging.getLogger("vote-extractor")

__all__ = (
    "VOTE_EXTRACTION_CONFIDENCE_THRESHOLD",
    "VOTE_EXTRACTION_CONTEXT_AFTER_CHARS",
    "VOTE_EXTRACTION_CONTEXT_BEFORE_CHARS",
    "VOTE_EXTRACTION_MAX_TOKENS",
    "VOTE_EXTRACTION_MIN_TEXT_CHARS",
    "LLM_EXTRACTED_VOTE_SOURCE",
    "SKIP_REASON_MISSING_TITLE",
    "SKIP_REASON_TRUSTED_SOURCE",
    "SKIP_REASON_ALREADY_HIGH_CONFIDENCE",
    "SKIP_REASON_EXISTING_RESULT",
    "SKIP_REASON_INSUFFICIENT_TEXT",
    "SKIP_REASON_LOW_CONFIDENCE",
    "SKIP_REASON_UNKNOWN_NO_TALLY",
    "VALID_OUTCOME_LABELS",
    "OUTCOME_SYNONYMS",
    "UNKNOWN_RESULT_VALUES",
    "TRUSTED_VOTE_SOURCES",
    "VOTE_KEYWORDS",
    "VoteExtractionModel",
    "AgendaItemLike",
    "AgendaItemQuery",
    "AgendaItemSession",
    "CatalogLike",
    "EventLike",
    "DocumentLike",
    "VoteExtractionCounters",
    "VoteExtractionResult",
    "prepare_vote_extraction_prompt",
    "normalize_outcome_label",
    "_extract_first_json_object",
    "_coerce_optional_int",
    "parse_vote_extraction_response",
    "extract_vote_outcome",
    "_build_vote_context_text",
    "_result_text_from_label",
    "_is_high_confidence_existing_llm_vote",
    "_is_trusted_existing_vote",
    "_has_non_unknown_result",
    "_apply_ambiguity_penalty",
    "run_vote_extraction_for_catalog",
    "AgendaItem",
    "logger",
)


def _vote_extraction_settings() -> VoteExtractionSettings:
    return VoteExtractionSettings(
        confidence_threshold=VOTE_EXTRACTION_CONFIDENCE_THRESHOLD,
        context_after_chars=VOTE_EXTRACTION_CONTEXT_AFTER_CHARS,
        context_before_chars=VOTE_EXTRACTION_CONTEXT_BEFORE_CHARS,
        max_tokens=VOTE_EXTRACTION_MAX_TOKENS,
        min_text_chars=VOTE_EXTRACTION_MIN_TEXT_CHARS,
    )


def _vote_extraction_runtime_hooks() -> VoteExtractionRuntimeHooks:
    return VoteExtractionRuntimeHooks(
        vote_extractor=extract_vote_outcome,
        context_builder=_build_vote_context_text,
        trusted_vote_checker=_is_trusted_existing_vote,
        high_confidence_vote_checker=_is_high_confidence_existing_llm_vote,
        existing_result_checker=_has_non_unknown_result,
        result_text_builder=_result_text_from_label,
    )


def prepare_vote_extraction_prompt(item_title: str, item_text: str, meeting_context: str = "") -> str:
    return _prepare_vote_extraction_prompt_impl(item_title, item_text, meeting_context)


def normalize_outcome_label(value: object) -> str:
    return _normalize_outcome_label_impl(value)


def _extract_first_json_object(text: str) -> str:
    return _extract_first_json_object_impl(text)


def _coerce_optional_int(value: object | None) -> int | None:
    return _coerce_optional_int_impl(value)


def parse_vote_extraction_response(raw_output: str, council_size: int | None = None) -> VoteExtractionResult:
    return _parse_vote_extraction_response_impl(raw_output, council_size)


def extract_vote_outcome(
    local_ai: VoteExtractionModel,
    item_title: str,
    item_text: str,
    meeting_context: str = "",
) -> VoteExtractionResult:
    settings = _vote_extraction_settings()
    prompt = prepare_vote_extraction_prompt(item_title, item_text, meeting_context)
    raw = local_ai.generate_json(prompt, max_tokens=settings.max_tokens)
    if not raw:
        raise ValueError("model returned empty vote extraction")
    parsed = parse_vote_extraction_response(raw)
    return _apply_ambiguity_penalty(
        parsed,
        item_text,
    )


def _build_vote_context_text(catalog_content: str, item_title: str, item_description: str | None) -> str:
    return _build_vote_context_text_impl(
        catalog_content,
        item_title,
        item_description,
        context_before_chars=VOTE_EXTRACTION_CONTEXT_BEFORE_CHARS,
        context_after_chars=VOTE_EXTRACTION_CONTEXT_AFTER_CHARS,
    )


def _result_text_from_label(outcome_label: str) -> str:
    return _result_text_from_label_impl(outcome_label)


def _is_high_confidence_existing_llm_vote(votes: object) -> bool:
    return _is_high_confidence_existing_llm_vote_impl(
        votes,
        confidence_threshold=VOTE_EXTRACTION_CONFIDENCE_THRESHOLD,
    )


def _is_trusted_existing_vote(votes: object) -> bool:
    return _is_trusted_existing_vote_impl(votes)


def _has_non_unknown_result(result_value: object | None) -> bool:
    return _has_non_unknown_result_impl(result_value)


def _apply_ambiguity_penalty(result: VoteExtractionResult, item_text: str) -> VoteExtractionResult:
    return _apply_ambiguity_penalty_impl(
        result,
        item_text,
        confidence_threshold=VOTE_EXTRACTION_CONFIDENCE_THRESHOLD,
        logger=logger,
    )


def run_vote_extraction_for_catalog(
    db: AgendaItemSession | None,
    local_ai: VoteExtractionModel,
    catalog: CatalogLike,
    doc: DocumentLike,
    *,
    force: bool = False,
    agenda_items: Sequence[AgendaItemLike] | None = None,
) -> VoteExtractionCounters:
    return _run_vote_extraction_for_catalog_impl(
        db,
        local_ai,
        catalog,
        doc,
        force=force,
        agenda_items=agenda_items,
        settings=_vote_extraction_settings(),
        logger=logger,
        prompt_builder=prepare_vote_extraction_prompt,
        runtime_hooks=_vote_extraction_runtime_hooks(),
    )

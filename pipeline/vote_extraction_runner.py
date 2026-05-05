from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
import logging

from pipeline.models import AgendaItem
from pipeline.vote_extraction_context import build_meeting_context, build_vote_context_text
from pipeline.vote_extraction_contracts import (
    LLM_EXTRACTED_VOTE_SOURCE,
    SKIP_REASON_ALREADY_HIGH_CONFIDENCE,
    SKIP_REASON_EXISTING_RESULT,
    SKIP_REASON_INSUFFICIENT_TEXT,
    SKIP_REASON_MISSING_TITLE,
    SKIP_REASON_TRUSTED_SOURCE,
    AgendaItemLike,
    AgendaItemSession,
    CatalogLike,
    CatalogVoteExtractor,
    DEFAULT_RUNTIME_HOOKS,
    DocumentLike,
    PromptBuilder,
    VoteExtractionCounters,
    VoteExtractionModel,
    VoteExtractionRuntimeHooks,
    VoteExtractionSettings,
    VoteExtractionResult,
)
from pipeline.vote_extraction_parser import parse_vote_extraction_response
from pipeline.vote_extraction_policy import (
    apply_ambiguity_penalty,
    has_non_unknown_result,
    is_high_confidence_existing_llm_vote,
    is_trusted_existing_vote,
    result_text_from_label,
    skip_reason_after_extraction,
)
from pipeline.vote_extraction_prompting import prepare_vote_extraction_prompt


def extract_vote_outcome(
    local_ai: VoteExtractionModel,
    item_title: str,
    item_text: str,
    meeting_context: str = "",
    *,
    settings: VoteExtractionSettings,
    logger: logging.Logger,
    prompt_builder: PromptBuilder = prepare_vote_extraction_prompt,
) -> VoteExtractionResult:
    prompt = prompt_builder(item_title, item_text, meeting_context)
    raw = local_ai.generate_json(prompt, max_tokens=settings.max_tokens)
    if not raw:
        raise ValueError("model returned empty vote extraction")
    parsed = parse_vote_extraction_response(raw)
    return apply_ambiguity_penalty(
        parsed,
        item_text,
        confidence_threshold=settings.confidence_threshold,
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
    settings: VoteExtractionSettings,
    logger: logging.Logger,
    prompt_builder: PromptBuilder = prepare_vote_extraction_prompt,
    runtime_hooks: VoteExtractionRuntimeHooks = DEFAULT_RUNTIME_HOOKS,
) -> VoteExtractionCounters:
    items = _agenda_items_for_catalog(db, catalog, agenda_items)
    counters = _empty_vote_counters()
    if not items:
        return counters

    meeting_context = build_meeting_context(getattr(doc, "event", None))
    for item in items:
        _process_agenda_item(
            item,
            catalog=catalog,
            local_ai=local_ai,
            force=force,
            counters=counters,
            meeting_context=meeting_context,
            settings=settings,
            logger=logger,
            prompt_builder=prompt_builder,
            runtime_hooks=runtime_hooks,
        )
    return counters


def _agenda_items_for_catalog(
    db: AgendaItemSession | None,
    catalog: CatalogLike,
    agenda_items: Sequence[AgendaItemLike] | None,
) -> list[AgendaItemLike]:
    items = list(agenda_items) if agenda_items is not None else None
    if items is not None:
        return items
    assert db is not None, "db session required when agenda_items are not provided"
    return db.query(AgendaItem).filter_by(catalog_id=catalog.id).order_by(AgendaItem.order).all()


def _empty_vote_counters() -> VoteExtractionCounters:
    return {
        "processed_items": 0,
        "updated_items": 0,
        "skipped_items": 0,
        "failed_items": 0,
        "skip_reasons": {},
    }


def _process_agenda_item(
    item: AgendaItemLike,
    *,
    catalog: CatalogLike,
    local_ai: VoteExtractionModel,
    force: bool,
    counters: VoteExtractionCounters,
    meeting_context: str,
    settings: VoteExtractionSettings,
    logger: logging.Logger,
    prompt_builder: PromptBuilder,
    runtime_hooks: VoteExtractionRuntimeHooks,
) -> None:
    item_title = str(getattr(item, "title", "") or "").strip()
    skip_reason = _skip_reason_before_extraction(
        item,
        item_title=item_title,
        force=force,
        settings=settings,
        runtime_hooks=runtime_hooks,
    )
    if skip_reason:
        _count_skip(counters, skip_reason)
        return

    context_builder = runtime_hooks.context_builder
    if context_builder is not None:
        context_text = context_builder(
            getattr(catalog, "content", "") or "", item_title, getattr(item, "description", None)
        )
    else:
        context_text = build_vote_context_text(
            getattr(catalog, "content", "") or "",
            item_title,
            getattr(item, "description", None),
            context_before_chars=settings.context_before_chars,
            context_after_chars=settings.context_after_chars,
        )
    if len(context_text) < settings.min_text_chars:
        _count_skip(counters, SKIP_REASON_INSUFFICIENT_TEXT)
        return

    extracted = _extract_vote_for_item(
        item,
        catalog=catalog,
        local_ai=local_ai,
        item_title=item_title,
        context_text=context_text,
        meeting_context=meeting_context,
        counters=counters,
        settings=settings,
        logger=logger,
        prompt_builder=prompt_builder,
        vote_extractor=runtime_hooks.vote_extractor,
    )
    if extracted is None:
        return

    skip_reason = skip_reason_after_extraction(extracted, settings=settings)
    if skip_reason:
        _count_skip(counters, skip_reason)
        return
    _update_item_vote(item, extracted, logger=logger, catalog=catalog, runtime_hooks=runtime_hooks)
    counters["updated_items"] += 1


def _skip_reason_before_extraction(
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


def _extract_vote_for_item(
    item: AgendaItemLike,
    *,
    catalog: CatalogLike,
    local_ai: VoteExtractionModel,
    item_title: str,
    context_text: str,
    meeting_context: str,
    counters: VoteExtractionCounters,
    settings: VoteExtractionSettings,
    logger: logging.Logger,
    prompt_builder: PromptBuilder,
    vote_extractor: CatalogVoteExtractor | None,
) -> VoteExtractionResult | None:
    counters["processed_items"] += 1
    try:
        if vote_extractor is not None:
            return vote_extractor(local_ai, item_title, context_text, meeting_context)
        return extract_vote_outcome(
            local_ai,
            item_title,
            context_text,
            meeting_context=meeting_context,
            settings=settings,
            logger=logger,
            prompt_builder=prompt_builder,
        )
    except Exception as exc:
        counters["failed_items"] += 1
        logger.warning(
            "vote_extraction.failed catalog_id=%s agenda_item_id=%s error=%s",
            catalog.id,
            getattr(item, "id", None),
            exc.__class__.__name__,
        )
        return None


def _update_item_vote(
    item: AgendaItemLike,
    extracted: VoteExtractionResult,
    *,
    logger: logging.Logger,
    catalog: CatalogLike,
    runtime_hooks: VoteExtractionRuntimeHooks,
) -> None:
    result_text_builder = runtime_hooks.result_text_builder or result_text_from_label
    item.result = result_text_builder(extracted.outcome_label)
    item.votes = {
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
        "extracted_at": datetime.now(timezone.utc).isoformat(),
    }
    logger.info(
        "vote_extraction.updated catalog_id=%s agenda_item_id=%s outcome=%s confidence=%.2f",
        catalog.id,
        getattr(item, "id", None),
        extracted.outcome_label,
        extracted.confidence,
    )


def _count_skip(counters: VoteExtractionCounters, reason: str) -> None:
    counters["skipped_items"] += 1
    counters["skip_reasons"][reason] = counters["skip_reasons"].get(reason, 0) + 1

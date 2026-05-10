from __future__ import annotations

from collections.abc import Sequence
import logging

from pipeline.models import AgendaItem
from pipeline.vote_extraction_context import build_meeting_context, build_vote_context_text
from pipeline.vote_extraction_contracts import (
    SKIP_REASON_INSUFFICIENT_TEXT,
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
from pipeline.vote_extraction_item import (
    count_failed_item,
    count_processed_item,
    count_skipped_item,
    count_updated_item,
    empty_vote_counters,
    log_extraction_failure,
    skip_reason_before_extraction,
    update_item_vote,
)
from pipeline.vote_extraction_parser import parse_vote_extraction_response
from pipeline.vote_extraction_policy import (
    apply_ambiguity_penalty,
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
    counters = empty_vote_counters()
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
        count_skipped_item(counters, skip_reason)
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
        count_skipped_item(counters, SKIP_REASON_INSUFFICIENT_TEXT)
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
        count_skipped_item(counters, skip_reason)
        return
    update_item_vote(item, extracted, logger=logger, catalog=catalog, runtime_hooks=runtime_hooks)
    count_updated_item(counters)


def _skip_reason_before_extraction(
    item: AgendaItemLike,
    *,
    item_title: str,
    force: bool,
    settings: VoteExtractionSettings,
    runtime_hooks: VoteExtractionRuntimeHooks,
) -> str | None:
    return skip_reason_before_extraction(
        item,
        item_title=item_title,
        force=force,
        settings=settings,
        runtime_hooks=runtime_hooks,
    )


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
    count_processed_item(counters)
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
        count_failed_item(counters)
        log_extraction_failure(item, catalog=catalog, logger=logger, error=exc)
        return None

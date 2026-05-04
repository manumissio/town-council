import logging
from dataclasses import dataclass
from typing import Protocol

from pipeline.agenda_summary_counters import (
    build_summary_counters,
    log_deterministic_fallback,
    log_grounding_pruned_lines,
    log_summary_counters,
)
from pipeline.agenda_summary_items import (
    AgendaSummaryItem,
    agenda_items_source_text,
    coerce_agenda_summary_item,
    serialize_item_for_filtering,
    should_drop_from_agenda_summary,
)
from pipeline.agenda_summary_prompting import prepare_structured_agenda_items_summary_prompt
from pipeline.agenda_summary_rendering import (
    agenda_items_summary_is_too_short,
    deterministic_agenda_items_summary,
    normalize_model_agenda_summary_output,
)
from pipeline.agenda_summary_scaffold import build_agenda_summary_scaffold
from pipeline.summary_quality import is_summary_grounded, prune_unsupported_summary_lines


class AgendaSummaryProvider(Protocol):
    def summarize_agenda_items(self, prompt: str, *, max_tokens: int, temperature: float) -> str | None: ...


@dataclass(frozen=True, slots=True)
class AgendaSummaryRuntimeConfig:
    temperature: float
    max_tokens: int
    max_bullets: int
    profile: str
    min_item_desc_chars: int
    min_substantive_desc_chars: int
    single_item_mode: str


@dataclass(frozen=True, slots=True)
class AgendaSummaryRequest:
    meeting_title: str
    meeting_date: str
    items: list[object] | None
    truncation_meta: dict[str, int] | None


@dataclass(frozen=True, slots=True)
class AgendaSummaryPreparedInput:
    structured_items: list[AgendaSummaryItem]
    filtered_items: list[AgendaSummaryItem]
    filtered_notice_fragments: int
    scaffold: dict[str, object]
    counters: dict[str, int]


def _structured_summary_items(items: list[object] | None) -> list[AgendaSummaryItem]:
    return [coerce_agenda_summary_item(item, index) for index, item in enumerate(items or [])]


def _filtered_summary_items(
    structured_items: list[AgendaSummaryItem],
    *,
    min_substantive_desc_chars: int,
) -> tuple[list[AgendaSummaryItem], int]:
    filtered_items = []
    filtered_notice_fragments = 0
    for item in structured_items:
        if should_drop_from_agenda_summary(
            serialize_item_for_filtering(item),
            min_substantive_desc_chars=min_substantive_desc_chars,
        ):
            filtered_notice_fragments += 1
            continue
        filtered_items.append(item)
    return filtered_items, filtered_notice_fragments


def _deterministic_fallback(
    *,
    logger: logging.Logger,
    counters: dict[str, int],
    items: list[AgendaSummaryItem],
    request: AgendaSummaryRequest,
    config: AgendaSummaryRuntimeConfig,
) -> str:
    log_deterministic_fallback(logger, counters)
    return deterministic_agenda_items_summary(
        items,
        config.max_bullets,
        request.truncation_meta,
        profile=config.profile,
        min_item_desc_chars=config.min_item_desc_chars,
        single_item_mode=config.single_item_mode,
    )


def _provider_summary(
    provider: AgendaSummaryProvider,
    *,
    prompt: str,
    max_tokens: int,
    temperature: float,
) -> str:
    return (provider.summarize_agenda_items(prompt, max_tokens=max_tokens, temperature=temperature) or "").strip()


def _grounded_summary(
    *,
    logger: logging.Logger,
    counters: dict[str, int],
    cleaned_summary: str,
    grounding_source: str,
) -> str:
    pruned_summary, removed_count = prune_unsupported_summary_lines(cleaned_summary, grounding_source)
    counters["agenda_summary_grounding_pruned_lines"] = int(removed_count)
    if removed_count:
        log_grounding_pruned_lines(logger, removed_count)
    return pruned_summary or cleaned_summary


def _prepare_agenda_summary_input(
    request: AgendaSummaryRequest,
    *,
    config: AgendaSummaryRuntimeConfig,
) -> AgendaSummaryPreparedInput:
    structured_items = _structured_summary_items(request.items)
    filtered_items, filtered_notice_fragments = _filtered_summary_items(
        structured_items,
        min_substantive_desc_chars=config.min_substantive_desc_chars,
    )
    scaffold = build_agenda_summary_scaffold(
        filtered_items,
        request.truncation_meta,
        profile=config.profile,
        max_bullets=config.max_bullets,
        min_item_desc_chars=config.min_item_desc_chars,
        single_item_mode=config.single_item_mode,
    )
    counters = build_summary_counters(structured_items, filtered_items, scaffold, request.truncation_meta)
    return AgendaSummaryPreparedInput(structured_items, filtered_items, filtered_notice_fragments, scaffold, counters)


def _log_prepared_input(logger: logging.Logger, prepared_input: AgendaSummaryPreparedInput) -> None:
    log_summary_counters(
        logger=logger,
        total_items=len(prepared_input.structured_items),
        filtered_items=len(prepared_input.filtered_items),
        filtered_notice_fragments=prepared_input.filtered_notice_fragments,
        counters=prepared_input.counters,
    )


def _provider_cleaned_summary(
    provider: AgendaSummaryProvider,
    request: AgendaSummaryRequest,
    prepared_input: AgendaSummaryPreparedInput,
    config: AgendaSummaryRuntimeConfig,
) -> tuple[str, str]:
    prompt = prepare_structured_agenda_items_summary_prompt(
        request.meeting_title,
        request.meeting_date,
        prepared_input.filtered_items,
        prepared_input.scaffold,
        request.truncation_meta,
    )
    grounding_source = agenda_items_source_text(prepared_input.filtered_items)
    raw_summary = _provider_summary(provider, prompt=prompt, max_tokens=config.max_tokens, temperature=config.temperature)
    return normalize_model_agenda_summary_output(raw_summary, prepared_input.scaffold), grounding_source


def run_agenda_summary_pipeline(
    provider: AgendaSummaryProvider,
    *,
    request: AgendaSummaryRequest,
    logger: logging.Logger,
    config: AgendaSummaryRuntimeConfig,
) -> str:
    prepared_input = _prepare_agenda_summary_input(request, config=config)
    _log_prepared_input(logger, prepared_input)

    if not prepared_input.filtered_items:
        return _deterministic_fallback(
            logger=logger,
            counters=prepared_input.counters,
            items=[],
            request=request,
            config=config,
        )

    cleaned_summary, grounding_source = _provider_cleaned_summary(provider, request, prepared_input, config)
    cleaned_summary = _grounded_summary(
        logger=logger,
        counters=prepared_input.counters,
        cleaned_summary=cleaned_summary,
        grounding_source=grounding_source,
    )

    grounded_summary = is_summary_grounded(cleaned_summary, grounding_source)
    if (not grounded_summary.is_grounded) or agenda_items_summary_is_too_short(cleaned_summary):
        return _deterministic_fallback(
            logger=logger,
            counters=prepared_input.counters,
            items=prepared_input.filtered_items,
            request=request,
            config=config,
        )
    return cleaned_summary

import logging
from typing import Protocol

from pipeline.agenda_summary_counters import (
    AGENDA_SUMMARY_COUNTERS_LOG,
    AGENDA_SUMMARY_FALLBACK_LOG,
    AGENDA_SUMMARY_GROUNDING_PRUNED_LOG,
)
from pipeline.agenda_summary_items import (
    agenda_items_source_text as _agenda_items_source_text,
    coerce_agenda_summary_item as _coerce_agenda_summary_item,
    serialize_item_for_filtering as _serialize_item_for_filtering,
    should_drop_from_agenda_summary as _should_drop_from_agenda_summary_impl,
    split_agenda_summary_item as _split_agenda_summary_item,
)
from pipeline.agenda_summary_pipeline import (
    AgendaSummaryRequest,
    AgendaSummaryRuntimeConfig,
    run_agenda_summary_pipeline as _run_agenda_summary_pipeline_impl,
)
from pipeline.agenda_summary_prompting import (
    prepare_agenda_items_summary_prompt as _prepare_agenda_items_summary_prompt_impl,
    prepare_structured_agenda_items_summary_prompt as _prepare_structured_agenda_items_summary_prompt,
)
from pipeline.agenda_summary_rendering import (
    agenda_items_summary_is_too_short as _agenda_items_summary_is_too_short,
    deterministic_agenda_items_summary as _deterministic_agenda_items_summary_impl,
    ensure_single_item_decision_section as _ensure_single_item_decision_section,
    normalize_model_agenda_summary_output as _normalize_model_agenda_summary_output,
)
from pipeline.agenda_summary_scaffold import (
    build_agenda_summary_scaffold as _build_agenda_summary_scaffold_impl,
    extract_money_snippets as _extract_money_snippets,
)
from pipeline.config import (
    AGENDA_MIN_SUBSTANTIVE_DESC_CHARS,
    AGENDA_SUMMARY_MAX_BULLETS,
    AGENDA_SUMMARY_MIN_ITEM_DESC_CHARS,
    AGENDA_SUMMARY_PROFILE,
    AGENDA_SUMMARY_SINGLE_ITEM_MODE,
    AGENDA_SUMMARY_TEMPERATURE,
    LLM_SUMMARY_MAX_TOKENS,
)


logger = logging.getLogger("local-ai")

__all__ = (
    "AGENDA_SUMMARY_COUNTERS_LOG",
    "AGENDA_SUMMARY_FALLBACK_LOG",
    "AGENDA_SUMMARY_GROUNDING_PRUNED_LOG",
    "AGENDA_SUMMARY_TEMPERATURE",
    "_agenda_items_source_text",
    "_agenda_items_summary_is_too_short",
    "_build_agenda_summary_scaffold",
    "_coerce_agenda_summary_item",
    "_ensure_single_item_decision_section",
    "_extract_money_snippets",
    "_normalize_model_agenda_summary_output",
    "_prepare_structured_agenda_items_summary_prompt",
    "_serialize_item_for_filtering",
    "_should_drop_from_agenda_summary",
    "_split_agenda_summary_item",
    "deterministic_agenda_items_summary",
    "prepare_agenda_items_summary_prompt",
    "run_agenda_summary_pipeline",
)


class AgendaSummaryProvider(Protocol):
    def summarize_agenda_items(self, prompt: str, *, max_tokens: int, temperature: float) -> str | None: ...


def _build_agenda_summary_scaffold(
    items: list[dict[str, object]],
    truncation_meta: dict[str, int] | None = None,
    profile: str = "decision_brief",
) -> dict[str, object]:
    return _build_agenda_summary_scaffold_impl(
        items,
        truncation_meta,
        profile=profile,
        max_bullets=AGENDA_SUMMARY_MAX_BULLETS,
        min_item_desc_chars=AGENDA_SUMMARY_MIN_ITEM_DESC_CHARS,
        single_item_mode=AGENDA_SUMMARY_SINGLE_ITEM_MODE,
    )


def prepare_agenda_items_summary_prompt(meeting_title: str, meeting_date: str, items: list[str]) -> str:
    return _prepare_agenda_items_summary_prompt_impl(
        meeting_title,
        meeting_date,
        items,
        profile=AGENDA_SUMMARY_PROFILE,
        max_bullets=AGENDA_SUMMARY_MAX_BULLETS,
        min_item_desc_chars=AGENDA_SUMMARY_MIN_ITEM_DESC_CHARS,
        single_item_mode=AGENDA_SUMMARY_SINGLE_ITEM_MODE,
    )


def deterministic_agenda_items_summary(
    items: list[object] | None,
    max_bullets: int = 25,
    truncation_meta: dict[str, int] | None = None,
) -> str:
    return _deterministic_agenda_items_summary_impl(
        items,
        max_bullets,
        truncation_meta,
        profile=AGENDA_SUMMARY_PROFILE,
        min_item_desc_chars=AGENDA_SUMMARY_MIN_ITEM_DESC_CHARS,
        single_item_mode=AGENDA_SUMMARY_SINGLE_ITEM_MODE,
    )


def _should_drop_from_agenda_summary(item_text: str) -> bool:
    return _should_drop_from_agenda_summary_impl(
        item_text,
        min_substantive_desc_chars=AGENDA_MIN_SUBSTANTIVE_DESC_CHARS,
    )


def run_agenda_summary_pipeline(
    provider: AgendaSummaryProvider,
    *,
    meeting_title: str,
    meeting_date: str,
    items: list[object] | None,
    truncation_meta: dict[str, int] | None,
) -> str:
    return _run_agenda_summary_pipeline_impl(
        provider,
        logger=logger,
        request=AgendaSummaryRequest(
            meeting_title=meeting_title,
            meeting_date=meeting_date,
            items=items,
            truncation_meta=truncation_meta,
        ),
        config=AgendaSummaryRuntimeConfig(
            temperature=AGENDA_SUMMARY_TEMPERATURE,
            max_tokens=LLM_SUMMARY_MAX_TOKENS,
            max_bullets=AGENDA_SUMMARY_MAX_BULLETS,
            profile=AGENDA_SUMMARY_PROFILE,
            min_item_desc_chars=AGENDA_SUMMARY_MIN_ITEM_DESC_CHARS,
            min_substantive_desc_chars=AGENDA_MIN_SUBSTANTIVE_DESC_CHARS,
            single_item_mode=AGENDA_SUMMARY_SINGLE_ITEM_MODE,
        ),
    )

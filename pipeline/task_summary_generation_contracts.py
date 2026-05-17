from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pipeline.llm import LocalAI
from pipeline.models import Catalog, Document

AGENDA_DOC_KIND = "agenda"
SUMMARY_COMPLETE_STATUS = "complete"
SUMMARY_CACHED_STATUS = "cached"
SUMMARY_STALE_STATUS = "stale"
SUMMARY_ERROR_STATUS = "error"
SUMMARY_BLOCKED_LOW_SIGNAL_STATUS = "blocked_low_signal"
SUMMARY_BLOCKED_UNGROUNDED_STATUS = "blocked_ungrounded"
SUMMARY_NONE_RETRY_ERROR = "AI Summarization returned None (Model missing or error)"


@dataclass(frozen=True)
class SummaryGenerationTaskServices:
    local_ai_factory: Callable[[], LocalAI]
    classify_catalog_bad_content: Callable[..., object]
    compute_content_hash: Callable[[str | None], str | None]
    normalize_summary_doc_kind: Callable[[str], str]
    analyze_source_text: Callable[[str], object]
    is_source_summarizable: Callable[[object], bool]
    build_low_signal_message: Callable[[object], str]
    build_agenda_summary_input_bundle: Callable[..., dict[str, Any]]
    is_summary_fresh: Callable[..., bool]
    compute_summary_source_hash: Callable[..., str | None]
    postprocess_extracted_text: Callable[[str | None], str]
    is_summary_grounded: Callable[[str, str], object]
    persist_agenda_summary: Callable[..., dict[str, Any]]
    reindex_catalog: Callable[[int], object]
    embed_catalog: Callable[[int], object]


@dataclass(frozen=True)
class SummaryTaskContext:
    db: Any
    catalog_id: int
    force: bool
    services: SummaryGenerationTaskServices


@dataclass(frozen=True)
class SummaryRecordContext:
    catalog: Catalog
    document: Document | None
    doc_kind: str
    content_hash: str | None


@dataclass(frozen=True)
class PreparedSummaryInput:
    agenda_items_hash: str | None
    agenda_summary_bundle: dict[str, Any] | None

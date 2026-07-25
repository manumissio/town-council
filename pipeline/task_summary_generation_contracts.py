from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pipeline.models import Catalog, Document
from sqlalchemy.orm import Session

AGENDA_DOC_KIND = "agenda"
SUMMARY_COMPLETE_STATUS = "complete"
SUMMARY_CACHED_STATUS = "cached"
SUMMARY_STALE_STATUS = "stale"
SUMMARY_ERROR_STATUS = "error"
SUMMARY_BLOCKED_LOW_SIGNAL_STATUS = "blocked_low_signal"
SUMMARY_BLOCKED_UNGROUNDED_STATUS = "blocked_ungrounded"
SUMMARY_NONE_RETRY_ERROR = "AI Summarization returned None (Model missing or error)"


@dataclass(frozen=True)
class SummaryTaskContext:
    db: Session
    catalog_id: int
    force: bool


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

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Final, NamedTuple, Protocol, TypeAlias, TypedDict


SqlExpression: TypeAlias = Any  # SQLAlchemy ORM expressions are dynamic across model classes.

MISSING_CONTENT_PATH: Final = "missing_content"
NEEDS_SEGMENTATION_PATH: Final = "not_generated_yet_needs_segmentation"
ELIGIBLE_AGENDA_SUMMARY_PATH: Final = "eligible_agenda_summary"
ELIGIBLE_NON_AGENDA_SUMMARY_PATH: Final = "eligible_non_agenda_summary"
BLOCKED_LOW_SIGNAL_PATH: Final = "blocked_low_signal"

AGENDA_SEGMENTATION_BLOCKED_ROOT_CAUSE: Final = "agenda_summaries_blocked_on_segmentation"
NON_AGENDA_UNSCHEDULED_ROOT_CAUSE: Final = "non_agenda_summaries_unscheduled"
QUALITY_GATE_ROOT_CAUSE: Final = "summary_quality_gate_blocking_non_agenda"
AGENDA_UNSCHEDULED_ROOT_CAUSE: Final = "agenda_summaries_unscheduled_after_segmentation"
NO_DOMINANT_BACKLOG_ROOT_CAUSE: Final = "no_dominant_backlog_detected"

AGENDA_DOC_KIND: Final = "agenda"
UNKNOWN_DOC_KIND: Final = "unknown"
NULL_SEGMENTATION_STATUS: Final = "<null>"
MISSING_SUMMARY_ROOT_CAUSE_RATIO_THRESHOLD: Final = 0.8

METRIC_SEMANTICS: Final[dict[str, str]] = {
    "catalogs_with_content": "cumulative_total",
    "catalogs_with_summary": "cumulative_total",
    "missing_summary_total": "unresolved_backlog",
    "agenda_missing_summary_total": "unresolved_backlog_agenda_only",
    "agenda_missing_summary_with_items": "unresolved_backlog_agenda_only_with_items",
    "agenda_missing_summary_without_items": "unresolved_backlog_agenda_only_without_items",
    "non_agenda_missing_summary_total": "unresolved_backlog_non_agenda_only",
    "agenda_segmentation_status_counts": "unresolved_backlog_only",
}

NON_AGENDA_SAMPLE_BUCKET: Final = "non_agenda_missing_summary"
AGENDA_WITH_ITEMS_SAMPLE_BUCKET: Final = "agenda_missing_summary_with_items"
AGENDA_WITHOUT_ITEMS_SAMPLE_BUCKET: Final = "agenda_missing_summary_without_items"


class CatalogModelLike(Protocol):
    id: SqlExpression
    content: SqlExpression
    summary: SqlExpression
    agenda_segmentation_status: SqlExpression


class DocumentModelLike(Protocol):
    id: SqlExpression
    catalog_id: SqlExpression
    category: SqlExpression
    event_id: SqlExpression


class AgendaItemModelLike(Protocol):
    id: SqlExpression
    catalog_id: SqlExpression


class EventModelLike(Protocol):
    id: SqlExpression
    source: SqlExpression


class SummaryHydrationModels(NamedTuple):
    agenda_item: AgendaItemModelLike
    catalog: CatalogModelLike
    document: DocumentModelLike
    event: EventModelLike | None


class NonAgendaMissingSummaryRow(NamedTuple):
    catalog_id: int
    content: str | None
    doc_kind: str


class SummaryHydrationSampleCatalogIds(TypedDict):
    non_agenda_missing_summary: list[int]
    agenda_missing_summary_with_items: list[int]
    agenda_missing_summary_without_items: list[int]


@dataclass(frozen=True)
class SummaryHydrationSnapshot:
    city: str | None
    catalogs_with_content: int
    catalogs_with_summary: int
    missing_summary_total: int
    agenda_missing_summary_total: int
    agenda_missing_summary_with_items: int
    agenda_missing_summary_without_items: int
    non_agenda_missing_summary_total: int
    non_agenda_summarizable: int
    non_agenda_blocked_low_signal: int
    agenda_segmentation_status_counts: dict[str, int]
    sample_catalog_ids: SummaryHydrationSampleCatalogIds
    likely_root_cause: str
    cumulative_catalogs_with_content: int = 0
    cumulative_catalogs_with_summary: int = 0
    unresolved_missing_summary_total: int = 0
    agenda_missing_summary_total_unresolved: int = 0
    agenda_missing_summary_with_items_unresolved: int = 0
    agenda_missing_summary_without_items_unresolved: int = 0
    non_agenda_missing_summary_total_unresolved: int = 0
    agenda_unresolved_segmentation_status_counts: dict[str, int] | None = None

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["metric_semantics"] = METRIC_SEMANTICS
        return payload

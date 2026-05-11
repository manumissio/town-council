from __future__ import annotations

from dataclasses import asdict, dataclass


METRIC_SEMANTICS = {
    "event_count": "distinct_events_by_record_month",
    "agenda_document_count": "distinct_agenda_documents_by_event_month",
    "agenda_catalog_count": "distinct_agenda_catalogs_by_event_month",
    "agenda_catalogs_with_content": "distinct_agenda_catalogs_with_non_empty_content_by_event_month",
    "agenda_catalogs_with_summary": "distinct_agenda_catalogs_with_non_empty_summary_by_event_month",
    "meeting_count": "distinct_record_date_plus_normalized_event_name_by_record_month",
}


@dataclass(frozen=True)
class MonthlyCoverageRow:
    month: str
    event_count: int
    meeting_count: int
    agenda_document_count: int
    agenda_catalog_count: int
    agenda_catalogs_with_content: int
    agenda_catalogs_with_summary: int
    source_event_counts: dict[str, int]
    source_meeting_counts: dict[str, int]
    flags: list[str]


@dataclass(frozen=True)
class CityCoverageAudit:
    city: str
    months: int
    date_from: str
    date_to: str
    expected_monthly_event_baseline: float
    below_expected_cadence_threshold: int | None
    expected_monthly_meeting_baseline: float
    below_expected_meeting_cadence_threshold: int | None
    totals: dict[str, int]
    source_counts: dict[str, int]
    monthly: list[MonthlyCoverageRow]
    suspicious_months: list[dict[str, object]]

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["metric_semantics"] = METRIC_SEMANTICS
        return payload

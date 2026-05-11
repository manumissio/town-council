from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from pipeline.city_coverage_windows import month_key, month_start, normalize_meeting_name


@dataclass
class MonthlyCoverageBucket:
    event_ids: set[int] = field(default_factory=set)
    meeting_keys: set[str] = field(default_factory=set)
    agenda_doc_ids: set[int] = field(default_factory=set)
    agenda_catalog_ids: set[int] = field(default_factory=set)
    content_catalog_ids: set[int] = field(default_factory=set)
    summary_catalog_ids: set[int] = field(default_factory=set)
    source_event_ids: dict[str, set[int]] = field(default_factory=dict)
    source_meeting_keys: dict[str, set[str]] = field(default_factory=dict)


def create_monthly_coverage_buckets(month_starts: list[date]) -> dict[str, MonthlyCoverageBucket]:
    return {month_key(month_start): MonthlyCoverageBucket() for month_start in month_starts}


def add_event_to_monthly_bucket(
    buckets: dict[str, MonthlyCoverageBucket],
    *,
    event_id: int,
    record_date: date,
    source: str,
    name: str | None,
) -> None:
    bucket = buckets.get(month_key(month_start(record_date)))
    if bucket is None:
        return

    normalized_event_id = int(event_id)
    meeting_key = f"{record_date.isoformat()}::{normalize_meeting_name(name)}"
    bucket.event_ids.add(normalized_event_id)
    bucket.meeting_keys.add(meeting_key)
    bucket.source_event_ids.setdefault(str(source), set()).add(normalized_event_id)
    bucket.source_meeting_keys.setdefault(str(source), set()).add(meeting_key)


def add_agenda_to_monthly_bucket(
    buckets: dict[str, MonthlyCoverageBucket],
    *,
    record_date: date,
    document_id: int,
    catalog_id: int | None,
    content: str | None,
    summary: str | None,
) -> None:
    bucket = buckets.get(month_key(month_start(record_date)))
    if bucket is None:
        return

    bucket.agenda_doc_ids.add(int(document_id))
    if catalog_id is None:
        return

    normalized_catalog_id = int(catalog_id)
    bucket.agenda_catalog_ids.add(normalized_catalog_id)
    if str(content or "").strip():
        bucket.content_catalog_ids.add(normalized_catalog_id)
    if str(summary or "").strip():
        bucket.summary_catalog_ids.add(normalized_catalog_id)

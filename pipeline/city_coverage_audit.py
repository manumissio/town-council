from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
import math
import re
import statistics

from pipeline.city_scope import source_aliases_for_city
from pipeline.models import Catalog, Document, Event


def _month_start(value: date) -> date:
    return value.replace(day=1)


def _shift_month(value: date, delta: int) -> date:
    year = value.year + ((value.month - 1 + delta) // 12)
    month = ((value.month - 1 + delta) % 12) + 1
    return date(year, month, 1)


def build_month_window(months: int, as_of: date | None = None) -> list[date]:
    if months <= 0:
        raise ValueError("months must be positive")
    anchor = _month_start(as_of or date.today())
    start = _shift_month(anchor, -(months - 1))
    return [_shift_month(start, idx) for idx in range(months)]


def month_key(value: date) -> str:
    return value.strftime("%Y-%m")


def normalize_meeting_name(value: str | None) -> str:
    normalized = re.sub(r"\s+", " ", str(value or "").strip().lower())
    return normalized or "(missing)"


def compute_expected_monthly_event_baseline(event_counts: list[int]) -> tuple[float, int | None]:
    if not event_counts:
        return 0.0, None
    baseline = float(statistics.median(event_counts))
    if baseline < 2.0:
        return baseline, None
    # Keep this conservative so the audit highlights suspicious troughs
    # without pretending to know each city's exact meeting cadence.
    threshold = max(1, int(math.ceil(baseline * 0.5)))
    return baseline, threshold


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
        payload["metric_semantics"] = {
            "event_count": "distinct_events_by_record_month",
            "agenda_document_count": "distinct_agenda_documents_by_event_month",
            "agenda_catalog_count": "distinct_agenda_catalogs_by_event_month",
            "agenda_catalogs_with_content": "distinct_agenda_catalogs_with_non_empty_content_by_event_month",
            "agenda_catalogs_with_summary": "distinct_agenda_catalogs_with_non_empty_summary_by_event_month",
            "meeting_count": "distinct_record_date_plus_normalized_event_name_by_record_month",
        }
        return payload


def build_city_coverage_audit(
    db_session,
    *,
    city: str,
    months: int = 12,
    as_of: date | None = None,
) -> CityCoverageAudit:
    month_starts = build_month_window(months, as_of=as_of)
    start_date = month_starts[0]
    end_date = as_of or date.today()
    source_aliases = sorted(source_aliases_for_city(city))

    monthly_sets: dict[str, dict[str, object]] = {}
    for month_start in month_starts:
        key = month_key(month_start)
        monthly_sets[key] = {
            "event_ids": set(),
            "meeting_keys": set(),
            "agenda_doc_ids": set(),
            "agenda_catalog_ids": set(),
            "content_catalog_ids": set(),
            "summary_catalog_ids": set(),
            "source_event_ids": {},
            "source_meeting_keys": {},
        }

    event_rows = (
        db_session.query(Event.id, Event.record_date, Event.source, Event.name)
        .filter(
            Event.source.in_(source_aliases),
            Event.record_date.isnot(None),
            Event.record_date >= start_date,
            Event.record_date <= end_date,
        )
        .all()
    )
    for event_id, record_date, source, name in event_rows:
        key = month_key(_month_start(record_date))
        bucket = monthly_sets.get(key)
        if bucket is None:
            continue
        bucket["event_ids"].add(int(event_id))
        # Cadence should approximate distinct meetings, not item-level event rows
        # emitted by some sources for the same meeting date/title combination.
        meeting_key = f"{record_date.isoformat()}::{normalize_meeting_name(name)}"
        bucket["meeting_keys"].add(meeting_key)
        source_event_ids = bucket["source_event_ids"]
        source_event_ids.setdefault(str(source), set()).add(int(event_id))
        source_meeting_keys = bucket["source_meeting_keys"]
        source_meeting_keys.setdefault(str(source), set()).add(meeting_key)

    agenda_rows = (
        db_session.query(
            Event.record_date,
            Document.id,
            Document.catalog_id,
            Catalog.content,
            Catalog.summary,
        )
        .join(Document, Document.event_id == Event.id)
        .outerjoin(Catalog, Catalog.id == Document.catalog_id)
        .filter(
            Event.source.in_(source_aliases),
            Event.record_date.isnot(None),
            Event.record_date >= start_date,
            Event.record_date <= end_date,
            Document.category == "agenda",
        )
        .all()
    )
    for record_date, document_id, catalog_id, content, summary in agenda_rows:
        key = month_key(_month_start(record_date))
        bucket = monthly_sets.get(key)
        if bucket is None:
            continue
        bucket["agenda_doc_ids"].add(int(document_id))
        if catalog_id is not None:
            normalized_catalog_id = int(catalog_id)
            bucket["agenda_catalog_ids"].add(normalized_catalog_id)
            if str(content or "").strip():
                bucket["content_catalog_ids"].add(normalized_catalog_id)
            if str(summary or "").strip():
                bucket["summary_catalog_ids"].add(normalized_catalog_id)

    event_counts = [len(bucket["event_ids"]) for bucket in monthly_sets.values()]
    meeting_counts = [len(bucket["meeting_keys"]) for bucket in monthly_sets.values()]
    event_baseline, event_cadence_threshold = compute_expected_monthly_event_baseline(event_counts)
    meeting_baseline, meeting_cadence_threshold = compute_expected_monthly_event_baseline(meeting_counts)
    current_month_key = month_key(_month_start(end_date))

    monthly_rows: list[MonthlyCoverageRow] = []
    suspicious_months: list[dict[str, object]] = []
    total_event_ids: set[int] = set()
    total_meeting_keys: set[str] = set()
    total_agenda_doc_ids: set[int] = set()
    total_agenda_catalog_ids: set[int] = set()
    total_content_catalog_ids: set[int] = set()
    total_summary_catalog_ids: set[int] = set()
    total_source_event_ids: dict[str, set[int]] = {}
    total_source_meeting_keys: dict[str, set[str]] = {}

    for key, bucket in monthly_sets.items():
        event_ids = bucket["event_ids"]
        meeting_keys = bucket["meeting_keys"]
        agenda_doc_ids = bucket["agenda_doc_ids"]
        agenda_catalog_ids = bucket["agenda_catalog_ids"]
        content_catalog_ids = bucket["content_catalog_ids"]
        summary_catalog_ids = bucket["summary_catalog_ids"]
        source_event_ids = bucket["source_event_ids"]
        source_meeting_keys = bucket["source_meeting_keys"]

        event_count = len(event_ids)
        meeting_count = len(meeting_keys)
        agenda_document_count = len(agenda_doc_ids)
        agenda_catalog_count = len(agenda_catalog_ids)
        agenda_catalogs_with_content = len(content_catalog_ids)
        agenda_catalogs_with_summary = len(summary_catalog_ids)

        flags: list[str] = []
        if event_count == 0:
            flags.append("no_events")
        if event_count > 0 and agenda_document_count == 0:
            flags.append("events_but_no_agendas")
        if agenda_document_count > 0 and agenda_catalogs_with_content == 0:
            flags.append("agendas_but_no_content")
        if agenda_catalogs_with_content > 0 and agenda_catalogs_with_summary == 0:
            flags.append("content_but_no_summaries")
        if (
            meeting_cadence_threshold is not None
            and key != current_month_key
            and meeting_count < meeting_cadence_threshold
        ):
            flags.append("below_expected_cadence")

        row = MonthlyCoverageRow(
            month=key,
            event_count=event_count,
            meeting_count=meeting_count,
            agenda_document_count=agenda_document_count,
            agenda_catalog_count=agenda_catalog_count,
            agenda_catalogs_with_content=agenda_catalogs_with_content,
            agenda_catalogs_with_summary=agenda_catalogs_with_summary,
            source_event_counts={source: len(ids) for source, ids in sorted(source_event_ids.items())},
            source_meeting_counts={source: len(keys) for source, keys in sorted(source_meeting_keys.items())},
            flags=flags,
        )
        monthly_rows.append(row)
        if flags:
            suspicious_months.append({"month": key, "flags": list(flags)})

        total_event_ids.update(event_ids)
        total_meeting_keys.update(meeting_keys)
        total_agenda_doc_ids.update(agenda_doc_ids)
        total_agenda_catalog_ids.update(agenda_catalog_ids)
        total_content_catalog_ids.update(content_catalog_ids)
        total_summary_catalog_ids.update(summary_catalog_ids)
        for source, ids in source_event_ids.items():
            total_source_event_ids.setdefault(source, set()).update(ids)
        for source, keys in source_meeting_keys.items():
            total_source_meeting_keys.setdefault(source, set()).update(keys)

    return CityCoverageAudit(
        city=city,
        months=months,
        date_from=start_date.isoformat(),
        date_to=end_date.isoformat(),
        expected_monthly_event_baseline=event_baseline,
        below_expected_cadence_threshold=event_cadence_threshold,
        expected_monthly_meeting_baseline=meeting_baseline,
        below_expected_meeting_cadence_threshold=meeting_cadence_threshold,
        totals={
            "event_count": len(total_event_ids),
            "meeting_count": len(total_meeting_keys),
            "agenda_document_count": len(total_agenda_doc_ids),
            "agenda_catalog_count": len(total_agenda_catalog_ids),
            "agenda_catalogs_with_content": len(total_content_catalog_ids),
            "agenda_catalogs_with_summary": len(total_summary_catalog_ids),
        },
        source_counts={source: len(ids) for source, ids in sorted(total_source_event_ids.items())},
        monthly=monthly_rows,
        suspicious_months=suspicious_months,
    )

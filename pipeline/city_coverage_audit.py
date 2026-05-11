from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from pipeline.city_coverage_assembly import build_coverage_summary
from pipeline.city_coverage_buckets import create_monthly_coverage_buckets
from pipeline.city_coverage_contracts import CityCoverageAudit as CityCoverageAudit
from pipeline.city_coverage_contracts import MonthlyCoverageRow as MonthlyCoverageRow
from pipeline.city_coverage_queries import ingest_coverage_rows, load_agenda_coverage_rows, load_event_coverage_rows
from pipeline.city_coverage_windows import (
    build_month_window,
    compute_expected_monthly_event_baseline,
    month_key,
    month_start,
    normalize_meeting_name as normalize_meeting_name,
)
from pipeline.city_scope import source_aliases_for_city


def build_city_coverage_audit(
    db_session: Session,
    *,
    city: str,
    months: int = 12,
    as_of: date | None = None,
) -> CityCoverageAudit:
    month_starts = build_month_window(months, as_of=as_of)
    start_date = month_starts[0]
    end_date = as_of or date.today()
    source_aliases = sorted(source_aliases_for_city(city))
    buckets = create_monthly_coverage_buckets(month_starts)

    ingest_coverage_rows(
        buckets,
        event_rows=load_event_coverage_rows(
            db_session,
            source_aliases=source_aliases,
            start_date=start_date,
            end_date=end_date,
        ),
        agenda_rows=load_agenda_coverage_rows(
            db_session,
            source_aliases=source_aliases,
            start_date=start_date,
            end_date=end_date,
        ),
    )

    event_counts = [len(bucket.event_ids) for bucket in buckets.values()]
    meeting_counts = [len(bucket.meeting_keys) for bucket in buckets.values()]
    event_baseline, event_cadence_threshold = compute_expected_monthly_event_baseline(event_counts)
    meeting_baseline, meeting_cadence_threshold = compute_expected_monthly_event_baseline(meeting_counts)
    summary = build_coverage_summary(
        buckets,
        current_month_key=month_key(month_start(end_date)),
        meeting_cadence_threshold=meeting_cadence_threshold,
    )

    return CityCoverageAudit(
        city=city,
        months=months,
        date_from=start_date.isoformat(),
        date_to=end_date.isoformat(),
        expected_monthly_event_baseline=event_baseline,
        below_expected_cadence_threshold=event_cadence_threshold,
        expected_monthly_meeting_baseline=meeting_baseline,
        below_expected_meeting_cadence_threshold=meeting_cadence_threshold,
        totals=summary.totals,
        source_counts=summary.source_counts,
        monthly=summary.monthly_rows,
        suspicious_months=summary.suspicious_months,
    )

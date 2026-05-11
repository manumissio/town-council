from __future__ import annotations

from dataclasses import dataclass

from pipeline.city_coverage_buckets import MonthlyCoverageBucket
from pipeline.city_coverage_contracts import MonthlyCoverageRow


@dataclass(frozen=True)
class CoverageSummary:
    monthly_rows: list[MonthlyCoverageRow]
    suspicious_months: list[dict[str, object]]
    totals: dict[str, int]
    source_counts: dict[str, int]


def build_coverage_summary(
    buckets: dict[str, MonthlyCoverageBucket],
    *,
    current_month_key: str,
    meeting_cadence_threshold: int | None,
) -> CoverageSummary:
    monthly_rows: list[MonthlyCoverageRow] = []
    suspicious_months: list[dict[str, object]] = []
    total_event_ids: set[int] = set()
    total_meeting_keys: set[str] = set()
    total_agenda_doc_ids: set[int] = set()
    total_agenda_catalog_ids: set[int] = set()
    total_content_catalog_ids: set[int] = set()
    total_summary_catalog_ids: set[int] = set()
    total_source_event_ids: dict[str, set[int]] = {}

    for key, bucket in buckets.items():
        row = build_monthly_coverage_row(
            key,
            bucket,
            current_month_key=current_month_key,
            meeting_cadence_threshold=meeting_cadence_threshold,
        )
        monthly_rows.append(row)
        if row.flags:
            suspicious_months.append({"month": key, "flags": list(row.flags)})

        total_event_ids.update(bucket.event_ids)
        total_meeting_keys.update(bucket.meeting_keys)
        total_agenda_doc_ids.update(bucket.agenda_doc_ids)
        total_agenda_catalog_ids.update(bucket.agenda_catalog_ids)
        total_content_catalog_ids.update(bucket.content_catalog_ids)
        total_summary_catalog_ids.update(bucket.summary_catalog_ids)
        for source, event_ids in bucket.source_event_ids.items():
            total_source_event_ids.setdefault(source, set()).update(event_ids)

    return CoverageSummary(
        monthly_rows=monthly_rows,
        suspicious_months=suspicious_months,
        totals={
            "event_count": len(total_event_ids),
            "meeting_count": len(total_meeting_keys),
            "agenda_document_count": len(total_agenda_doc_ids),
            "agenda_catalog_count": len(total_agenda_catalog_ids),
            "agenda_catalogs_with_content": len(total_content_catalog_ids),
            "agenda_catalogs_with_summary": len(total_summary_catalog_ids),
        },
        source_counts={source: len(event_ids) for source, event_ids in sorted(total_source_event_ids.items())},
    )


def build_monthly_coverage_row(
    month: str,
    bucket: MonthlyCoverageBucket,
    *,
    current_month_key: str,
    meeting_cadence_threshold: int | None,
) -> MonthlyCoverageRow:
    flags = build_monthly_flags(
        month,
        event_count=len(bucket.event_ids),
        agenda_document_count=len(bucket.agenda_doc_ids),
        agenda_catalogs_with_content=len(bucket.content_catalog_ids),
        agenda_catalogs_with_summary=len(bucket.summary_catalog_ids),
        meeting_count=len(bucket.meeting_keys),
        current_month_key=current_month_key,
        meeting_cadence_threshold=meeting_cadence_threshold,
    )
    return MonthlyCoverageRow(
        month=month,
        event_count=len(bucket.event_ids),
        meeting_count=len(bucket.meeting_keys),
        agenda_document_count=len(bucket.agenda_doc_ids),
        agenda_catalog_count=len(bucket.agenda_catalog_ids),
        agenda_catalogs_with_content=len(bucket.content_catalog_ids),
        agenda_catalogs_with_summary=len(bucket.summary_catalog_ids),
        source_event_counts={source: len(event_ids) for source, event_ids in sorted(bucket.source_event_ids.items())},
        source_meeting_counts={source: len(keys) for source, keys in sorted(bucket.source_meeting_keys.items())},
        flags=flags,
    )


def build_monthly_flags(
    month: str,
    *,
    event_count: int,
    agenda_document_count: int,
    agenda_catalogs_with_content: int,
    agenda_catalogs_with_summary: int,
    meeting_count: int,
    current_month_key: str,
    meeting_cadence_threshold: int | None,
) -> list[str]:
    monthly_flag_checks = [
        ("no_events", event_count == 0),
        ("events_but_no_agendas", event_count > 0 and agenda_document_count == 0),
        ("agendas_but_no_content", agenda_document_count > 0 and agenda_catalogs_with_content == 0),
        ("content_but_no_summaries", agenda_catalogs_with_content > 0 and agenda_catalogs_with_summary == 0),
        (
            "below_expected_cadence",
            meeting_cadence_threshold is not None and month != current_month_key and meeting_count < meeting_cadence_threshold,
        ),
    ]
    return [flag for flag, should_report in monthly_flag_checks if should_report]

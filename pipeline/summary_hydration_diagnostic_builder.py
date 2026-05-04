from __future__ import annotations

from dataclasses import asdict

from sqlalchemy.orm import Session

from pipeline.summary_hydration_diagnostic_contracts import (
    BLOCKED_LOW_SIGNAL_PATH,
    ELIGIBLE_NON_AGENDA_SUMMARY_PATH,
    NonAgendaMissingSummaryRow,
    SummaryHydrationSampleCatalogIds,
    SummaryHydrationSnapshot,
)
from pipeline.summary_hydration_diagnostic_policy import infer_primary_root_cause, predict_summary_path
from pipeline.summary_hydration_diagnostic_queries import (
    build_doc_kind_subquery,
    build_scoped_catalog_ids,
    count_agenda_missing_summaries,
    count_catalogs_with_required_field,
    load_non_agenda_missing_summary_rows,
    load_sample_catalog_ids,
    load_segmentation_status_counts,
    load_summary_hydration_models,
)


def _classify_non_agenda_backlog(rows: list[NonAgendaMissingSummaryRow]) -> tuple[int, int]:
    non_agenda_summarizable = 0
    non_agenda_blocked_low_signal = 0
    for row in rows:
        predicted_path = predict_summary_path(
            row.doc_kind,
            has_content=True,
            has_agenda_items=False,
            content=row.content,
        )
        if predicted_path == ELIGIBLE_NON_AGENDA_SUMMARY_PATH:
            non_agenda_summarizable += 1
        elif predicted_path == BLOCKED_LOW_SIGNAL_PATH:
            non_agenda_blocked_low_signal += 1
    return non_agenda_summarizable, non_agenda_blocked_low_signal


def _build_provisional_snapshot(
    *,
    city: str | None,
    catalogs_with_content: int,
    catalogs_with_summary: int,
    agenda_missing_summary_total: int,
    agenda_missing_summary_with_items: int,
    non_agenda_rows: list[NonAgendaMissingSummaryRow],
    non_agenda_summarizable: int,
    non_agenda_blocked_low_signal: int,
    segmentation_status_counts: dict[str, int],
    sample_catalog_ids: SummaryHydrationSampleCatalogIds,
) -> SummaryHydrationSnapshot:
    missing_summary_total = max(0, catalogs_with_content - catalogs_with_summary)
    agenda_missing_summary_without_items = max(0, agenda_missing_summary_total - agenda_missing_summary_with_items)
    non_agenda_missing_summary_total = len(non_agenda_rows)
    return SummaryHydrationSnapshot(
        city=city,
        catalogs_with_content=catalogs_with_content,
        catalogs_with_summary=catalogs_with_summary,
        missing_summary_total=missing_summary_total,
        agenda_missing_summary_total=agenda_missing_summary_total,
        agenda_missing_summary_with_items=agenda_missing_summary_with_items,
        agenda_missing_summary_without_items=agenda_missing_summary_without_items,
        non_agenda_missing_summary_total=non_agenda_missing_summary_total,
        non_agenda_summarizable=non_agenda_summarizable,
        non_agenda_blocked_low_signal=non_agenda_blocked_low_signal,
        agenda_segmentation_status_counts=segmentation_status_counts,
        sample_catalog_ids=sample_catalog_ids,
        likely_root_cause="pending",
        cumulative_catalogs_with_content=catalogs_with_content,
        cumulative_catalogs_with_summary=catalogs_with_summary,
        unresolved_missing_summary_total=missing_summary_total,
        agenda_missing_summary_total_unresolved=agenda_missing_summary_total,
        agenda_missing_summary_with_items_unresolved=agenda_missing_summary_with_items,
        agenda_missing_summary_without_items_unresolved=agenda_missing_summary_without_items,
        non_agenda_missing_summary_total_unresolved=non_agenda_missing_summary_total,
        agenda_unresolved_segmentation_status_counts=segmentation_status_counts,
    )


def build_summary_hydration_snapshot(
    db_session: Session,
    sample_limit: int = 5,
    city: str | None = None,
) -> SummaryHydrationSnapshot:
    models = load_summary_hydration_models(include_event=bool(city))
    doc_kind_subquery = build_doc_kind_subquery(db_session, models.document)
    scoped_catalog_ids = build_scoped_catalog_ids(
        db_session,
        city=city,
        catalog_model=models.catalog,
        document_model=models.document,
        event_model=models.event,
    )
    catalogs_with_content = count_catalogs_with_required_field(
        db_session,
        catalog_model=models.catalog,
        scoped_catalog_ids=scoped_catalog_ids,
        catalog_field=models.catalog.content,
    )
    catalogs_with_summary = count_catalogs_with_required_field(
        db_session,
        catalog_model=models.catalog,
        scoped_catalog_ids=scoped_catalog_ids,
        catalog_field=models.catalog.summary,
    )
    agenda_missing_summary_total, agenda_missing_summary_with_items = count_agenda_missing_summaries(
        db_session,
        catalog_model=models.catalog,
        doc_kind_subquery=doc_kind_subquery,
        scoped_catalog_ids=scoped_catalog_ids,
        agenda_item_model=models.agenda_item,
    )
    non_agenda_rows = load_non_agenda_missing_summary_rows(
        db_session,
        catalog_model=models.catalog,
        doc_kind_subquery=doc_kind_subquery,
        scoped_catalog_ids=scoped_catalog_ids,
    )
    non_agenda_summarizable, non_agenda_blocked_low_signal = _classify_non_agenda_backlog(non_agenda_rows)
    segmentation_status_counts = load_segmentation_status_counts(
        db_session,
        catalog_model=models.catalog,
        scoped_catalog_ids=scoped_catalog_ids,
    )
    sample_catalog_ids = load_sample_catalog_ids(
        db_session,
        catalog_model=models.catalog,
        agenda_item_model=models.agenda_item,
        doc_kind_subquery=doc_kind_subquery,
        scoped_catalog_ids=scoped_catalog_ids,
        sample_limit=sample_limit,
    )
    provisional_snapshot = _build_provisional_snapshot(
        city=city,
        catalogs_with_content=catalogs_with_content,
        catalogs_with_summary=catalogs_with_summary,
        agenda_missing_summary_total=agenda_missing_summary_total,
        agenda_missing_summary_with_items=agenda_missing_summary_with_items,
        non_agenda_rows=non_agenda_rows,
        non_agenda_summarizable=non_agenda_summarizable,
        non_agenda_blocked_low_signal=non_agenda_blocked_low_signal,
        segmentation_status_counts=segmentation_status_counts,
        sample_catalog_ids=sample_catalog_ids,
    )
    return SummaryHydrationSnapshot(
        **{
            **asdict(provisional_snapshot),
            "likely_root_cause": infer_primary_root_cause(provisional_snapshot),
        }
    )

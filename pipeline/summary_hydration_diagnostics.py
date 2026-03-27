from __future__ import annotations

from dataclasses import asdict, dataclass

from sqlalchemy import and_, func

from pipeline.city_scope import source_aliases_for_city
from pipeline.models import AgendaItem, Catalog, Document
from pipeline.summary_quality import analyze_source_text, is_source_summarizable


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
    sample_catalog_ids: dict[str, list[int]]
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
        payload["metric_semantics"] = {
            "catalogs_with_content": "cumulative_total",
            "catalogs_with_summary": "cumulative_total",
            "missing_summary_total": "unresolved_backlog",
            "agenda_missing_summary_total": "unresolved_backlog_agenda_only",
            "agenda_missing_summary_with_items": "unresolved_backlog_agenda_only_with_items",
            "agenda_missing_summary_without_items": "unresolved_backlog_agenda_only_without_items",
            "non_agenda_missing_summary_total": "unresolved_backlog_non_agenda_only",
            "agenda_segmentation_status_counts": "unresolved_backlog_only",
        }
        return payload


def predict_summary_path(doc_kind: str | None, *, has_content: bool, has_agenda_items: bool, content: str | None) -> str:
    normalized_kind = (doc_kind or "").strip().lower()
    if not has_content:
        return "missing_content"
    if normalized_kind == "agenda":
        if not has_agenda_items:
            return "not_generated_yet_needs_segmentation"
        return "eligible_agenda_summary"
    quality = analyze_source_text(content or "")
    if not is_source_summarizable(quality):
        return "blocked_low_signal"
    return "eligible_non_agenda_summary"


def infer_primary_root_cause(snapshot: SummaryHydrationSnapshot) -> str:
    if (
        snapshot.agenda_missing_summary_without_items > 0
        and snapshot.agenda_missing_summary_without_items >= snapshot.missing_summary_total * 0.8
    ):
        return "agenda_summaries_blocked_on_segmentation"
    if snapshot.non_agenda_summarizable > 0:
        return "non_agenda_summaries_unscheduled"
    if snapshot.non_agenda_blocked_low_signal > 0:
        return "summary_quality_gate_blocking_non_agenda"
    if snapshot.agenda_missing_summary_with_items > 0:
        return "agenda_summaries_unscheduled_after_segmentation"
    return "no_dominant_backlog_detected"


def build_summary_hydration_snapshot(db_session, sample_limit: int = 5, city: str | None = None) -> SummaryHydrationSnapshot:
    first_document_subquery = (
        db_session.query(
            Document.catalog_id.label("catalog_id"),
            func.min(Document.id).label("document_id"),
        )
        .group_by(Document.catalog_id)
        .subquery("first_document")
    )
    doc_kind_subquery = (
        db_session.query(
            Document.catalog_id.label("catalog_id"),
            func.lower(func.coalesce(Document.category, "")).label("doc_kind"),
        )
        .join(
            first_document_subquery,
            and_(
                Document.catalog_id == first_document_subquery.c.catalog_id,
                Document.id == first_document_subquery.c.document_id,
            ),
        )
        .subquery("doc_kind")
    )
    base_catalog_ids = (
        db_session.query(Catalog.id)
        .join(Document, Document.catalog_id == Catalog.id)
    )
    if city:
        from pipeline.models import Event

        base_catalog_ids = base_catalog_ids.join(Event, Event.id == Document.event_id).filter(
            Event.source.in_(sorted(source_aliases_for_city(city)))
        )
    scoped_catalog_ids = base_catalog_ids.distinct().subquery("scoped_catalog_ids")

    catalogs_with_content = (
        db_session.query(func.count(Catalog.id))
        .join(scoped_catalog_ids, scoped_catalog_ids.c.id == Catalog.id)
        .filter(Catalog.content.isnot(None), Catalog.content != "")
        .scalar()
        or 0
    )
    catalogs_with_summary = (
        db_session.query(func.count(Catalog.id))
        .join(scoped_catalog_ids, scoped_catalog_ids.c.id == Catalog.id)
        .filter(Catalog.summary.isnot(None), Catalog.summary != "")
        .scalar()
        or 0
    )
    missing_summary_total = max(0, int(catalogs_with_content) - int(catalogs_with_summary))

    agenda_missing_summary_total = (
        db_session.query(func.count(func.distinct(Catalog.id)))
        .join(scoped_catalog_ids, scoped_catalog_ids.c.id == Catalog.id)
        .join(doc_kind_subquery, doc_kind_subquery.c.catalog_id == Catalog.id)
        .filter(
            Catalog.content.isnot(None),
            Catalog.content != "",
            Catalog.summary.is_(None),
            doc_kind_subquery.c.doc_kind == "agenda",
        )
        .scalar()
        or 0
    )
    agenda_missing_summary_with_items = (
        db_session.query(func.count(func.distinct(Catalog.id)))
        .join(scoped_catalog_ids, scoped_catalog_ids.c.id == Catalog.id)
        .join(doc_kind_subquery, doc_kind_subquery.c.catalog_id == Catalog.id)
        .join(AgendaItem, AgendaItem.catalog_id == Catalog.id)
        .filter(
            Catalog.content.isnot(None),
            Catalog.content != "",
            Catalog.summary.is_(None),
            doc_kind_subquery.c.doc_kind == "agenda",
        )
        .scalar()
        or 0
    )
    agenda_missing_summary_without_items = max(
        0,
        int(agenda_missing_summary_total) - int(agenda_missing_summary_with_items),
    )

    non_agenda_rows = (
        db_session.query(Catalog.id, Catalog.content, doc_kind_subquery.c.doc_kind)
        .join(scoped_catalog_ids, scoped_catalog_ids.c.id == Catalog.id)
        .join(doc_kind_subquery, doc_kind_subquery.c.catalog_id == Catalog.id)
        .filter(
            Catalog.content.isnot(None),
            Catalog.content != "",
            Catalog.summary.is_(None),
            doc_kind_subquery.c.doc_kind != "agenda",
        )
        .all()
    )
    non_agenda_summarizable = 0
    non_agenda_blocked_low_signal = 0
    for row in non_agenda_rows:
        predicted = predict_summary_path(
            row.doc_kind,
            has_content=True,
            has_agenda_items=False,
            content=row.content,
        )
        if predicted == "eligible_non_agenda_summary":
            non_agenda_summarizable += 1
        elif predicted == "blocked_low_signal":
            non_agenda_blocked_low_signal += 1

    segmentation_status_counts = {
        str(status): int(count)
        for status, count in (
            db_session.query(
                func.coalesce(Catalog.agenda_segmentation_status, "<null>"),
                func.count(Catalog.id),
            )
            .join(scoped_catalog_ids, scoped_catalog_ids.c.id == Catalog.id)
            .filter(
                Catalog.content.isnot(None),
                Catalog.content != "",
                Catalog.summary.is_(None),
            )
            .group_by(func.coalesce(Catalog.agenda_segmentation_status, "<null>"))
            .all()
        )
    }

    sample_catalog_ids = {
        "non_agenda_missing_summary": [
            row[0]
            for row in (
                db_session.query(Catalog.id)
                .join(scoped_catalog_ids, scoped_catalog_ids.c.id == Catalog.id)
                .join(doc_kind_subquery, doc_kind_subquery.c.catalog_id == Catalog.id)
                .filter(
                    Catalog.content.isnot(None),
                    Catalog.content != "",
                    Catalog.summary.is_(None),
                    doc_kind_subquery.c.doc_kind != "agenda",
                )
                .order_by(Catalog.id)
                .limit(sample_limit)
                .all()
            )
        ],
        "agenda_missing_summary_with_items": [
            row[0]
            for row in (
                db_session.query(Catalog.id)
                .join(scoped_catalog_ids, scoped_catalog_ids.c.id == Catalog.id)
                .join(doc_kind_subquery, doc_kind_subquery.c.catalog_id == Catalog.id)
                .join(AgendaItem, AgendaItem.catalog_id == Catalog.id)
                .filter(
                    Catalog.content.isnot(None),
                    Catalog.content != "",
                    Catalog.summary.is_(None),
                    doc_kind_subquery.c.doc_kind == "agenda",
                )
                .order_by(Catalog.id)
                .distinct()
                .limit(sample_limit)
                .all()
            )
        ],
        "agenda_missing_summary_without_items": [
            row[0]
            for row in (
                db_session.query(Catalog.id)
                .join(scoped_catalog_ids, scoped_catalog_ids.c.id == Catalog.id)
                .join(doc_kind_subquery, doc_kind_subquery.c.catalog_id == Catalog.id)
                .outerjoin(AgendaItem, AgendaItem.catalog_id == Catalog.id)
                .filter(
                    Catalog.content.isnot(None),
                    Catalog.content != "",
                    Catalog.summary.is_(None),
                    doc_kind_subquery.c.doc_kind == "agenda",
                    AgendaItem.id.is_(None),
                )
                .order_by(Catalog.id)
                .limit(sample_limit)
                .all()
            )
        ],
    }

    provisional_snapshot = SummaryHydrationSnapshot(
        city=city,
        catalogs_with_content=int(catalogs_with_content),
        catalogs_with_summary=int(catalogs_with_summary),
        missing_summary_total=missing_summary_total,
        agenda_missing_summary_total=int(agenda_missing_summary_total),
        agenda_missing_summary_with_items=int(agenda_missing_summary_with_items),
        agenda_missing_summary_without_items=int(agenda_missing_summary_without_items),
        non_agenda_missing_summary_total=len(non_agenda_rows),
        non_agenda_summarizable=non_agenda_summarizable,
        non_agenda_blocked_low_signal=non_agenda_blocked_low_signal,
        agenda_segmentation_status_counts=segmentation_status_counts,
        sample_catalog_ids=sample_catalog_ids,
        likely_root_cause="pending",
        cumulative_catalogs_with_content=int(catalogs_with_content),
        cumulative_catalogs_with_summary=int(catalogs_with_summary),
        unresolved_missing_summary_total=missing_summary_total,
        agenda_missing_summary_total_unresolved=int(agenda_missing_summary_total),
        agenda_missing_summary_with_items_unresolved=int(agenda_missing_summary_with_items),
        agenda_missing_summary_without_items_unresolved=int(agenda_missing_summary_without_items),
        non_agenda_missing_summary_total_unresolved=len(non_agenda_rows),
        agenda_unresolved_segmentation_status_counts=segmentation_status_counts,
    )
    return SummaryHydrationSnapshot(
        **{
            **asdict(provisional_snapshot),
            "likely_root_cause": infer_primary_root_cause(provisional_snapshot),
        }
    )

from __future__ import annotations

from dataclasses import asdict, dataclass

from sqlalchemy import and_, func

from pipeline.models import AgendaItem, Catalog, Document
from pipeline.summary_quality import analyze_source_text, is_source_summarizable


@dataclass(frozen=True)
class SummaryHydrationSnapshot:
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

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


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


def build_summary_hydration_snapshot(db_session, sample_limit: int = 5) -> SummaryHydrationSnapshot:
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

    catalogs_with_content = (
        db_session.query(func.count(Catalog.id))
        .filter(Catalog.content.isnot(None), Catalog.content != "")
        .scalar()
        or 0
    )
    catalogs_with_summary = (
        db_session.query(func.count(Catalog.id))
        .filter(Catalog.summary.isnot(None), Catalog.summary != "")
        .scalar()
        or 0
    )
    missing_summary_total = max(0, int(catalogs_with_content) - int(catalogs_with_summary))

    agenda_missing_summary_total = (
        db_session.query(func.count(func.distinct(Catalog.id)))
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
    )
    return SummaryHydrationSnapshot(
        **{
            **provisional_snapshot.to_dict(),
            "likely_root_cause": infer_primary_root_cause(provisional_snapshot),
        }
    )

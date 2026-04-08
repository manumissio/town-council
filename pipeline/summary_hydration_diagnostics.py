from __future__ import annotations

from dataclasses import asdict, dataclass
from importlib import import_module
from typing import Any, Final, NamedTuple, Protocol, TypedDict

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from pipeline.city_scope import source_aliases_for_city
from pipeline.document_kinds import normalize_summary_doc_kind, summary_doc_kind_sql_expr
from pipeline.summary_quality import analyze_source_text, is_source_summarizable


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
    id: Any
    content: Any
    summary: Any
    agenda_segmentation_status: Any


class DocumentModelLike(Protocol):
    id: Any
    catalog_id: Any
    category: Any
    event_id: Any


class AgendaItemModelLike(Protocol):
    id: Any
    catalog_id: Any


class EventModelLike(Protocol):
    id: Any
    source: Any


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


def _load_summary_hydration_models(*, include_event: bool) -> SummaryHydrationModels:
    # Runtime-loaded model symbols keep this diagnostic boundary typeable without
    # widening the strict subtree into the entire ORM layer.
    models_module = import_module("pipeline.models")
    event_model: EventModelLike | None = models_module.Event if include_event else None
    return SummaryHydrationModels(
        agenda_item=models_module.AgendaItem,
        catalog=models_module.Catalog,
        document=models_module.Document,
        event=event_model,
    )


def predict_summary_path(
    doc_kind: str | None,
    *,
    has_content: bool,
    has_agenda_items: bool,
    content: str | None,
) -> str:
    normalized_kind = normalize_summary_doc_kind(doc_kind)
    if not has_content:
        return MISSING_CONTENT_PATH
    if normalized_kind == AGENDA_DOC_KIND:
        if not has_agenda_items:
            return NEEDS_SEGMENTATION_PATH
        return ELIGIBLE_AGENDA_SUMMARY_PATH
    quality = analyze_source_text(content or "")
    if not is_source_summarizable(quality):
        return BLOCKED_LOW_SIGNAL_PATH
    return ELIGIBLE_NON_AGENDA_SUMMARY_PATH


def infer_primary_root_cause(snapshot: SummaryHydrationSnapshot) -> str:
    if (
        snapshot.agenda_missing_summary_without_items > 0
        and snapshot.agenda_missing_summary_without_items
        >= snapshot.missing_summary_total * MISSING_SUMMARY_ROOT_CAUSE_RATIO_THRESHOLD
    ):
        return AGENDA_SEGMENTATION_BLOCKED_ROOT_CAUSE
    if snapshot.non_agenda_summarizable > 0:
        return NON_AGENDA_UNSCHEDULED_ROOT_CAUSE
    if snapshot.non_agenda_blocked_low_signal > 0:
        return QUALITY_GATE_ROOT_CAUSE
    if snapshot.agenda_missing_summary_with_items > 0:
        return AGENDA_UNSCHEDULED_ROOT_CAUSE
    return NO_DOMINANT_BACKLOG_ROOT_CAUSE


def _build_first_document_subquery(db_session: Session, document_model: DocumentModelLike) -> Any:
    return (
        db_session.query(
            document_model.catalog_id.label("catalog_id"),
            func.min(document_model.id).label("document_id"),
        )
        .group_by(document_model.catalog_id)
        .subquery("first_document")
    )


def _build_doc_kind_subquery(db_session: Session, document_model: DocumentModelLike) -> Any:
    first_document_subquery = _build_first_document_subquery(db_session, document_model)
    return (
        db_session.query(
            document_model.catalog_id.label("catalog_id"),
            summary_doc_kind_sql_expr(document_model.category).label("doc_kind"),
        )
        .join(
            first_document_subquery,
            and_(
                document_model.catalog_id == first_document_subquery.c.catalog_id,
                document_model.id == first_document_subquery.c.document_id,
            ),
        )
        .subquery("doc_kind")
    )


def _build_scoped_catalog_ids(
    db_session: Session,
    *,
    city: str | None,
    catalog_model: CatalogModelLike,
    document_model: DocumentModelLike,
    event_model: EventModelLike | None,
) -> Any:
    base_catalog_ids = db_session.query(catalog_model.id).join(
        document_model, document_model.catalog_id == catalog_model.id
    )
    if city:
        if event_model is None:
            raise RuntimeError("Event model is required for city-scoped hydration diagnostics")
        base_catalog_ids = base_catalog_ids.join(event_model, event_model.id == document_model.event_id).filter(
            event_model.source.in_(sorted(source_aliases_for_city(city)))
        )
    return base_catalog_ids.distinct().subquery("scoped_catalog_ids")


def _count_catalogs_with_content(
    db_session: Session, *, catalog_model: CatalogModelLike, scoped_catalog_ids: Any
) -> int:
    return int(
        db_session.query(func.count(catalog_model.id))
        .join(scoped_catalog_ids, scoped_catalog_ids.c.id == catalog_model.id)
        .filter(catalog_model.content.isnot(None), catalog_model.content != "")
        .scalar()
        or 0
    )


def _count_catalogs_with_summary(
    db_session: Session, *, catalog_model: CatalogModelLike, scoped_catalog_ids: Any
) -> int:
    return int(
        db_session.query(func.count(catalog_model.id))
        .join(scoped_catalog_ids, scoped_catalog_ids.c.id == catalog_model.id)
        .filter(catalog_model.summary.isnot(None), catalog_model.summary != "")
        .scalar()
        or 0
    )


def _count_agenda_missing_summaries(
    db_session: Session,
    *,
    catalog_model: CatalogModelLike,
    doc_kind_subquery: Any,
    scoped_catalog_ids: Any,
    agenda_item_model: Any,
) -> tuple[int, int]:
    base_query = (
        db_session.query(func.count(func.distinct(catalog_model.id)))
        .join(scoped_catalog_ids, scoped_catalog_ids.c.id == catalog_model.id)
        .join(doc_kind_subquery, doc_kind_subquery.c.catalog_id == catalog_model.id)
        .filter(
            catalog_model.content.isnot(None),
            catalog_model.content != "",
            catalog_model.summary.is_(None),
            doc_kind_subquery.c.doc_kind == AGENDA_DOC_KIND,
        )
    )
    agenda_missing_summary_total = int(base_query.scalar() or 0)
    agenda_missing_summary_with_items = int(
        base_query.join(agenda_item_model, agenda_item_model.catalog_id == catalog_model.id).scalar() or 0
    )
    return agenda_missing_summary_total, agenda_missing_summary_with_items


def _load_non_agenda_missing_summary_rows(
    db_session: Session,
    *,
    catalog_model: CatalogModelLike,
    doc_kind_subquery: Any,
    scoped_catalog_ids: Any,
) -> list[NonAgendaMissingSummaryRow]:
    raw_rows = (
        db_session.query(catalog_model.id, catalog_model.content, doc_kind_subquery.c.doc_kind)
        .join(scoped_catalog_ids, scoped_catalog_ids.c.id == catalog_model.id)
        .join(doc_kind_subquery, doc_kind_subquery.c.catalog_id == catalog_model.id)
        .filter(
            catalog_model.content.isnot(None),
            catalog_model.content != "",
            catalog_model.summary.is_(None),
            doc_kind_subquery.c.doc_kind != AGENDA_DOC_KIND,
        )
        .all()
    )
    return [
        NonAgendaMissingSummaryRow(
            catalog_id=int(catalog_id),
            content=content,
            doc_kind=str(doc_kind or UNKNOWN_DOC_KIND),
        )
        for catalog_id, content, doc_kind in raw_rows
    ]


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


def _load_segmentation_status_counts(
    db_session: Session,
    *,
    catalog_model: CatalogModelLike,
    scoped_catalog_ids: Any,
) -> dict[str, int]:
    raw_counts = (
        db_session.query(
            func.coalesce(catalog_model.agenda_segmentation_status, NULL_SEGMENTATION_STATUS),
            func.count(catalog_model.id),
        )
        .join(scoped_catalog_ids, scoped_catalog_ids.c.id == catalog_model.id)
        .filter(
            catalog_model.content.isnot(None),
            catalog_model.content != "",
            catalog_model.summary.is_(None),
        )
        .group_by(func.coalesce(catalog_model.agenda_segmentation_status, NULL_SEGMENTATION_STATUS))
        .all()
    )
    return {str(status): int(count) for status, count in raw_counts}


def _load_sample_catalog_ids(
    db_session: Session,
    *,
    catalog_model: CatalogModelLike,
    agenda_item_model: Any,
    doc_kind_subquery: Any,
    scoped_catalog_ids: Any,
    sample_limit: int,
) -> SummaryHydrationSampleCatalogIds:
    non_agenda_missing_summary = [
        int(catalog_id)
        for (catalog_id,) in (
            db_session.query(catalog_model.id)
            .join(scoped_catalog_ids, scoped_catalog_ids.c.id == catalog_model.id)
            .join(doc_kind_subquery, doc_kind_subquery.c.catalog_id == catalog_model.id)
            .filter(
                catalog_model.content.isnot(None),
                catalog_model.content != "",
                catalog_model.summary.is_(None),
                doc_kind_subquery.c.doc_kind != AGENDA_DOC_KIND,
            )
            .order_by(catalog_model.id)
            .limit(sample_limit)
            .all()
        )
    ]
    agenda_missing_summary_with_items = [
        int(catalog_id)
        for (catalog_id,) in (
            db_session.query(catalog_model.id)
            .join(scoped_catalog_ids, scoped_catalog_ids.c.id == catalog_model.id)
            .join(doc_kind_subquery, doc_kind_subquery.c.catalog_id == catalog_model.id)
            .join(agenda_item_model, agenda_item_model.catalog_id == catalog_model.id)
            .filter(
                catalog_model.content.isnot(None),
                catalog_model.content != "",
                catalog_model.summary.is_(None),
                doc_kind_subquery.c.doc_kind == AGENDA_DOC_KIND,
            )
            .order_by(catalog_model.id)
            .distinct()
            .limit(sample_limit)
            .all()
        )
    ]
    agenda_missing_summary_without_items = [
        int(catalog_id)
        for (catalog_id,) in (
            db_session.query(catalog_model.id)
            .join(scoped_catalog_ids, scoped_catalog_ids.c.id == catalog_model.id)
            .join(doc_kind_subquery, doc_kind_subquery.c.catalog_id == catalog_model.id)
            .outerjoin(agenda_item_model, agenda_item_model.catalog_id == catalog_model.id)
            .filter(
                catalog_model.content.isnot(None),
                catalog_model.content != "",
                catalog_model.summary.is_(None),
                doc_kind_subquery.c.doc_kind == AGENDA_DOC_KIND,
                agenda_item_model.id.is_(None),
            )
            .order_by(catalog_model.id)
            .limit(sample_limit)
            .all()
        )
    ]
    return SummaryHydrationSampleCatalogIds(
        non_agenda_missing_summary=non_agenda_missing_summary,
        agenda_missing_summary_with_items=agenda_missing_summary_with_items,
        agenda_missing_summary_without_items=agenda_missing_summary_without_items,
    )


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
    models = _load_summary_hydration_models(include_event=bool(city))
    doc_kind_subquery = _build_doc_kind_subquery(db_session, models.document)
    scoped_catalog_ids = _build_scoped_catalog_ids(
        db_session,
        city=city,
        catalog_model=models.catalog,
        document_model=models.document,
        event_model=models.event,
    )

    catalogs_with_content = _count_catalogs_with_content(
        db_session,
        catalog_model=models.catalog,
        scoped_catalog_ids=scoped_catalog_ids,
    )
    catalogs_with_summary = _count_catalogs_with_summary(
        db_session,
        catalog_model=models.catalog,
        scoped_catalog_ids=scoped_catalog_ids,
    )
    agenda_missing_summary_total, agenda_missing_summary_with_items = _count_agenda_missing_summaries(
        db_session,
        catalog_model=models.catalog,
        doc_kind_subquery=doc_kind_subquery,
        scoped_catalog_ids=scoped_catalog_ids,
        agenda_item_model=models.agenda_item,
    )
    non_agenda_rows = _load_non_agenda_missing_summary_rows(
        db_session,
        catalog_model=models.catalog,
        doc_kind_subquery=doc_kind_subquery,
        scoped_catalog_ids=scoped_catalog_ids,
    )
    non_agenda_summarizable, non_agenda_blocked_low_signal = _classify_non_agenda_backlog(non_agenda_rows)
    segmentation_status_counts = _load_segmentation_status_counts(
        db_session,
        catalog_model=models.catalog,
        scoped_catalog_ids=scoped_catalog_ids,
    )
    sample_catalog_ids = _load_sample_catalog_ids(
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

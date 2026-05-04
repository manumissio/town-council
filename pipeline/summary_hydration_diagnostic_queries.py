from importlib import import_module
from typing import Any, cast

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from pipeline.city_scope import source_aliases_for_city
from pipeline.document_kinds import summary_doc_kind_sql_expr
from pipeline.summary_hydration_diagnostic_contracts import (
    AGENDA_DOC_KIND,
    AgendaItemModelLike,
    CatalogModelLike,
    DocumentModelLike,
    EventModelLike,
    NonAgendaMissingSummaryRow,
    NULL_SEGMENTATION_STATUS,
    SqlExpression,
    SummaryHydrationModels,
    SummaryHydrationSampleCatalogIds,
    UNKNOWN_DOC_KIND,
)


def _orm_join_target(model: object) -> Any:
    return cast(Any, model)  # Runtime-loaded SQLAlchemy model.


def load_summary_hydration_models(*, include_event: bool) -> SummaryHydrationModels:
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


def build_doc_kind_subquery(db_session: Session, document_model: DocumentModelLike) -> SqlExpression:
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


def _build_first_document_subquery(db_session: Session, document_model: DocumentModelLike) -> SqlExpression:
    return (
        db_session.query(
            document_model.catalog_id.label("catalog_id"),
            func.min(document_model.id).label("document_id"),
        )
        .group_by(document_model.catalog_id)
        .subquery("first_document")
    )


def build_scoped_catalog_ids(
    db_session: Session,
    *,
    city: str | None,
    catalog_model: CatalogModelLike,
    document_model: DocumentModelLike,
    event_model: EventModelLike | None,
) -> SqlExpression:
    base_catalog_ids = db_session.query(catalog_model.id).join(
        _orm_join_target(document_model), document_model.catalog_id == catalog_model.id
    )
    if city:
        if event_model is None:
            raise RuntimeError("Event model is required for city-scoped hydration diagnostics")
        base_catalog_ids = base_catalog_ids.join(
            _orm_join_target(event_model), event_model.id == document_model.event_id
        ).filter(event_model.source.in_(sorted(source_aliases_for_city(city))))
    return base_catalog_ids.distinct().subquery("scoped_catalog_ids")


def count_catalogs_with_required_field(
    db_session: Session,
    *,
    catalog_model: CatalogModelLike,
    scoped_catalog_ids: SqlExpression,
    catalog_field: SqlExpression,
) -> int:
    return int(
        db_session.query(func.count(catalog_model.id))
        .join(scoped_catalog_ids, scoped_catalog_ids.c.id == catalog_model.id)
        .filter(catalog_field.isnot(None), catalog_field != "")
        .scalar()
        or 0
    )


def count_agenda_missing_summaries(
    db_session: Session,
    *,
    catalog_model: CatalogModelLike,
    doc_kind_subquery: SqlExpression,
    scoped_catalog_ids: SqlExpression,
    agenda_item_model: AgendaItemModelLike,
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
        base_query.join(_orm_join_target(agenda_item_model), agenda_item_model.catalog_id == catalog_model.id).scalar()
        or 0
    )
    return agenda_missing_summary_total, agenda_missing_summary_with_items


def load_non_agenda_missing_summary_rows(
    db_session: Session,
    *,
    catalog_model: CatalogModelLike,
    doc_kind_subquery: SqlExpression,
    scoped_catalog_ids: SqlExpression,
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


def load_segmentation_status_counts(
    db_session: Session,
    *,
    catalog_model: CatalogModelLike,
    scoped_catalog_ids: SqlExpression,
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


def load_sample_catalog_ids(
    db_session: Session,
    *,
    catalog_model: CatalogModelLike,
    agenda_item_model: AgendaItemModelLike,
    doc_kind_subquery: SqlExpression,
    scoped_catalog_ids: SqlExpression,
    sample_limit: int,
) -> SummaryHydrationSampleCatalogIds:
    return SummaryHydrationSampleCatalogIds(
        non_agenda_missing_summary=_non_agenda_missing_summary_ids(
            db_session,
            catalog_model=catalog_model,
            doc_kind_subquery=doc_kind_subquery,
            scoped_catalog_ids=scoped_catalog_ids,
            sample_limit=sample_limit,
        ),
        agenda_missing_summary_with_items=_agenda_missing_summary_with_items_ids(
            db_session,
            catalog_model=catalog_model,
            agenda_item_model=agenda_item_model,
            doc_kind_subquery=doc_kind_subquery,
            scoped_catalog_ids=scoped_catalog_ids,
            sample_limit=sample_limit,
        ),
        agenda_missing_summary_without_items=_agenda_missing_summary_without_items_ids(
            db_session,
            catalog_model=catalog_model,
            agenda_item_model=agenda_item_model,
            doc_kind_subquery=doc_kind_subquery,
            scoped_catalog_ids=scoped_catalog_ids,
            sample_limit=sample_limit,
        ),
    )


def _non_agenda_missing_summary_ids(
    db_session: Session,
    *,
    catalog_model: CatalogModelLike,
    doc_kind_subquery: SqlExpression,
    scoped_catalog_ids: SqlExpression,
    sample_limit: int,
) -> list[int]:
    query = (
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
    )
    return _catalog_ids(query)


def _agenda_missing_summary_with_items_ids(
    db_session: Session,
    *,
    catalog_model: CatalogModelLike,
    agenda_item_model: AgendaItemModelLike,
    doc_kind_subquery: SqlExpression,
    scoped_catalog_ids: SqlExpression,
    sample_limit: int,
) -> list[int]:
    query = (
        db_session.query(catalog_model.id)
        .join(scoped_catalog_ids, scoped_catalog_ids.c.id == catalog_model.id)
        .join(doc_kind_subquery, doc_kind_subquery.c.catalog_id == catalog_model.id)
        .join(_orm_join_target(agenda_item_model), agenda_item_model.catalog_id == catalog_model.id)
        .filter(
            catalog_model.content.isnot(None),
            catalog_model.content != "",
            catalog_model.summary.is_(None),
            doc_kind_subquery.c.doc_kind == AGENDA_DOC_KIND,
        )
        .order_by(catalog_model.id)
        .distinct()
        .limit(sample_limit)
    )
    return _catalog_ids(query)


def _agenda_missing_summary_without_items_ids(
    db_session: Session,
    *,
    catalog_model: CatalogModelLike,
    agenda_item_model: AgendaItemModelLike,
    doc_kind_subquery: SqlExpression,
    scoped_catalog_ids: SqlExpression,
    sample_limit: int,
) -> list[int]:
    query = (
        db_session.query(catalog_model.id)
        .join(scoped_catalog_ids, scoped_catalog_ids.c.id == catalog_model.id)
        .join(doc_kind_subquery, doc_kind_subquery.c.catalog_id == catalog_model.id)
        .outerjoin(_orm_join_target(agenda_item_model), agenda_item_model.catalog_id == catalog_model.id)
        .filter(
            catalog_model.content.isnot(None),
            catalog_model.content != "",
            catalog_model.summary.is_(None),
            doc_kind_subquery.c.doc_kind == AGENDA_DOC_KIND,
            agenda_item_model.id.is_(None),
        )
        .order_by(catalog_model.id)
        .limit(sample_limit)
    )
    return _catalog_ids(query)


def _catalog_ids(query: SqlExpression) -> list[int]:
    return [int(catalog_id) for (catalog_id,) in query.all()]

from typing import Any, cast

from sqlalchemy.orm import Session

from pipeline.summary_hydration_diagnostic_contracts import (
    AGENDA_DOC_KIND,
    AgendaItemModelLike,
    CatalogModelLike,
    SqlExpression,
    SummaryHydrationSampleCatalogIds,
)


def _orm_join_target(model: object) -> Any:
    return cast(Any, model)  # Runtime-loaded SQLAlchemy model.


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

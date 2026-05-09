from sqlalchemy import and_, func, or_

from pipeline.city_scope import source_aliases_for_city
from pipeline.document_kinds import summary_doc_kind_sql_expr
from pipeline.models import AgendaItem, Catalog, Document, Event
from pipeline.profiling import apply_catalog_id_scope


def summary_doc_kind_subquery(db):
    first_document = (
        db.query(
            Document.catalog_id.label("catalog_id"),
            func.min(Document.id).label("document_id"),
        )
        .group_by(Document.catalog_id)
        .subquery("first_document")
    )
    return (
        db.query(
            Document.catalog_id.label("catalog_id"),
            summary_doc_kind_sql_expr(Document.category).label("doc_kind"),
        )
        .join(
            first_document,
            and_(
                Document.catalog_id == first_document.c.catalog_id,
                Document.id == first_document.c.document_id,
            ),
        )
        .subquery("summary_doc_kind")
    )


def select_catalog_ids_for_summary_hydration(
    db,
    limit: int | None = None,
    city: str | None = None,
) -> list[int]:
    """
    Select catalogs eligible for batch summary hydration.

    Agenda catalogs are included only when structured agenda items already exist,
    which keeps the batch path aligned with the interactive summary contract.
    """
    doc_kind = summary_doc_kind_subquery(db)
    agenda_items_exist = db.query(AgendaItem.id).filter(AgendaItem.catalog_id == Catalog.id).exists()
    query = (
        db.query(Catalog.id)
        .join(doc_kind, doc_kind.c.catalog_id == Catalog.id)
        .join(Document, Document.catalog_id == Catalog.id)
        .join(Event, Event.id == Document.event_id)
        .filter(
            Catalog.content.isnot(None),
            Catalog.content != "",
            or_(
                and_(
                    doc_kind.c.doc_kind != "agenda",
                    or_(
                        Catalog.summary.is_(None),
                        Catalog.summary_source_hash.is_(None),
                        Catalog.content_hash.is_(None),
                        Catalog.summary_source_hash != Catalog.content_hash,
                    ),
                ),
                and_(
                    doc_kind.c.doc_kind == "agenda",
                    agenda_items_exist,
                    or_(
                        Catalog.summary.is_(None),
                        Catalog.summary_source_hash.is_(None),
                        Catalog.agenda_items_hash.is_(None),
                        Catalog.summary_source_hash != Catalog.agenda_items_hash,
                    ),
                ),
            ),
        )
        .order_by(Catalog.id)
    )
    query = apply_catalog_id_scope(query, Catalog.id)
    if city:
        query = query.filter(Event.source.in_(sorted(source_aliases_for_city(city))))
    if limit is not None:
        query = query.limit(limit)
    return [row[0] for row in query.distinct().all()]


def summary_doc_kind_map(db, catalog_ids: list[int]) -> dict[int, str]:
    if not catalog_ids:
        return {}
    doc_kind = summary_doc_kind_subquery(db)
    rows = db.query(doc_kind.c.catalog_id, doc_kind.c.doc_kind).filter(doc_kind.c.catalog_id.in_(catalog_ids)).all()
    return {int(catalog_id): str(kind or "unknown") for catalog_id, kind in rows}

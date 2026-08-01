from sqlalchemy.orm import Session as SQLAlchemySession

from pipeline.content_hash import compute_content_hash
from pipeline.document_kinds import normalize_summary_doc_kind
from pipeline.models import AgendaItem, Catalog, Document
from pipeline.summary_freshness import compute_agenda_items_hash


def resolve_summary_source_hashes(
    db: SQLAlchemySession,
    catalog_id: int,
    catalog: Catalog,
) -> tuple[str, str | None, str | None]:
    document = db.query(Document).filter_by(catalog_id=catalog_id).first()
    doc_kind = normalize_summary_doc_kind(document.category if document else "unknown")
    content_hash = catalog.content_hash or (compute_content_hash(catalog.content) if catalog.content else None)
    agenda_items_hash = catalog.agenda_items_hash
    if doc_kind == "agenda":
        agenda_items = (
            db.query(AgendaItem)
            .filter_by(catalog_id=catalog_id)
            .order_by(AgendaItem.order)
            .all()
        )
        agenda_items_hash = compute_agenda_items_hash(agenda_items)
    return doc_kind, content_hash, agenda_items_hash

from sqlalchemy import or_

from pipeline.config import AGENDA_BATCH_SIZE
from pipeline.db_session import db_session
from pipeline.llm import LocalAI
from pipeline.models import AgendaItem, Catalog, Document
from pipeline.vote_extractor import run_vote_extraction_for_catalog


def extract_votes_for_catalog(catalog_id: int, force: bool = False):
    local_ai = LocalAI()
    with db_session() as session:
        catalog = session.get(Catalog, catalog_id)
        if not catalog:
            return None
        doc = session.query(Document).filter_by(catalog_id=catalog_id).first()
        if not doc:
            return None

        items = (
            session.query(AgendaItem)
            .filter_by(catalog_id=catalog_id)
            .order_by(AgendaItem.order)
            .all()
        )
        if not items:
            return {
                "catalog_id": catalog_id,
                "processed_items": 0,
                "updated_items": 0,
                "skipped_items": 0,
                "failed_items": 0,
                "skip_reasons": {"no_items": 1},
            }

        counters = run_vote_extraction_for_catalog(
            session,
            local_ai,
            catalog,
            doc,
            force=force,
            agenda_items=items,
        )
        session.commit()
        return {"catalog_id": catalog_id, **counters}


def extract_votes_batch(force: bool = False):
    with db_session() as session:
        rows = (
            session.query(Catalog.id)
            .join(Document, Document.catalog_id == Catalog.id)
            .join(AgendaItem, AgendaItem.catalog_id == Catalog.id)
            .filter(
                Catalog.content.isnot(None),
                Catalog.content != "",
                or_(AgendaItem.votes.is_(None), AgendaItem.result.is_(None), AgendaItem.result == ""),
            )
            .distinct()
            .limit(AGENDA_BATCH_SIZE)
            .all()
        )
        ids = [row[0] for row in rows]

    results = []
    for catalog_id in ids:
        result = extract_votes_for_catalog(catalog_id, force=force)
        if result:
            results.append(result)
    return results


if __name__ == "__main__":
    extract_votes_batch(force=False)

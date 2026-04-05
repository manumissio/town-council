import logging

from pipeline.content_hash import compute_content_hash
from pipeline.db_session import db_session
from pipeline.document_kinds import normalize_summary_doc_kind
from pipeline.models import AgendaItem, Catalog, Document
from pipeline.summary_freshness import compute_agenda_items_hash, compute_summary_source_hash

logger = logging.getLogger("backfill_catalog_hashes")


def backfill(limit: int | None = None) -> dict:
    """
    Backfill content_hash + source hashes for existing rows.

    Safe defaults:
    - If a catalog already has a derived value (summary/topics) but no source hash,
      we assume it was generated from the then-current content and mark it fresh.
      Users can still force-regenerate if needed.
    """
    updated = 0
    skipped = 0
    with db_session() as session:
        q = session.query(Catalog).order_by(Catalog.id.asc())
        if limit is not None:
            q = q.limit(limit)

        for c in q:
            if not c.content:
                skipped += 1
                continue

            changed = False
            content_hash = c.content_hash or compute_content_hash(c.content)
            if content_hash and content_hash != c.content_hash:
                c.content_hash = content_hash
                changed = True

            doc = session.query(Document).filter_by(catalog_id=c.id).first()
            doc_kind = normalize_summary_doc_kind(doc.category if doc else "unknown")
            agenda_items_hash = c.agenda_items_hash
            if doc_kind == "agenda":
                agenda_items = (
                    session.query(AgendaItem)
                    .filter_by(catalog_id=c.id)
                    .order_by(AgendaItem.order)
                    .all()
                )
                computed_agenda_items_hash = compute_agenda_items_hash(agenda_items)
                if computed_agenda_items_hash != c.agenda_items_hash:
                    c.agenda_items_hash = computed_agenda_items_hash
                    changed = True
                agenda_items_hash = computed_agenda_items_hash

            summary_source_hash = compute_summary_source_hash(
                doc_kind,
                content_hash=content_hash,
                agenda_items_hash=agenda_items_hash,
            )

            if c.summary and not c.summary_source_hash and summary_source_hash:
                c.summary_source_hash = summary_source_hash
                changed = True

            if c.topics is not None and not c.topics_source_hash and content_hash:
                c.topics_source_hash = content_hash
                changed = True

            if c.entities is not None and not c.entities_source_hash and content_hash:
                c.entities_source_hash = content_hash
                changed = True

            if changed:
                updated += 1

        session.commit()

    return {"status": "ok", "updated": updated, "skipped": skipped}


def main() -> int:
    logging.basicConfig(level=logging.INFO)
    logger.info("catalog_hash_backfill_complete payload=%s", backfill())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

import logging

from pipeline.content_hash import compute_content_hash
from pipeline.db_session import db_session
from pipeline.document_kinds import normalize_summary_doc_kind
from pipeline.models import AgendaItem, Catalog, Document
from pipeline.profiling import apply_catalog_id_scope
from pipeline.summary_freshness import compute_agenda_items_hash, compute_summary_source_hash

logger = logging.getLogger("backfill_catalog_hashes")


def _hash_needs_backfill(source_hash, *, preserve_explicit_hashes: bool) -> bool:
    return source_hash is None or (not preserve_explicit_hashes and source_hash == "")


def _normalize_catalog_hashes_for_catalog(session, catalog, *, preserve_explicit_hashes: bool) -> bool:
    changed = False
    content_hash = catalog.content_hash
    if _hash_needs_backfill(content_hash, preserve_explicit_hashes=preserve_explicit_hashes):
        content_hash = compute_content_hash(catalog.content)
        if content_hash and content_hash != catalog.content_hash:
            catalog.content_hash = content_hash
            changed = True

    doc = session.query(Document).filter_by(catalog_id=catalog.id).first()
    doc_kind = normalize_summary_doc_kind(doc.category if doc else "unknown")
    agenda_items_hash = catalog.agenda_items_hash
    if doc_kind == "agenda":
        agenda_items = (
            session.query(AgendaItem)
            .filter_by(catalog_id=catalog.id)
            .order_by(AgendaItem.order, AgendaItem.id)
            .all()
        )
        computed_agenda_items_hash = compute_agenda_items_hash(agenda_items)
        if computed_agenda_items_hash != catalog.agenda_items_hash and (
            not preserve_explicit_hashes or catalog.agenda_items_hash is None
        ):
            catalog.agenda_items_hash = computed_agenda_items_hash
            changed = True
        agenda_items_hash = computed_agenda_items_hash

    summary_source_hash = compute_summary_source_hash(
        doc_kind,
        content_hash=content_hash,
        agenda_items_hash=agenda_items_hash,
        agenda_segmentation_status=getattr(catalog, "agenda_segmentation_status", None),
    )
    if (
        catalog.summary
        and _hash_needs_backfill(
            catalog.summary_source_hash,
            preserve_explicit_hashes=preserve_explicit_hashes,
        )
        and summary_source_hash
    ):
        catalog.summary_source_hash = summary_source_hash
        changed = True
    if (
        catalog.topics is not None
        and _hash_needs_backfill(catalog.topics_source_hash, preserve_explicit_hashes=preserve_explicit_hashes)
        and content_hash
    ):
        catalog.topics_source_hash = content_hash
        changed = True
    if (
        catalog.entities is not None
        and _hash_needs_backfill(catalog.entities_source_hash, preserve_explicit_hashes=preserve_explicit_hashes)
        and content_hash
    ):
        catalog.entities_source_hash = content_hash
        changed = True
    return changed


def normalize_catalog_hashes(
    session,
    *,
    catalog_ids: list[int] | None = None,
    limit: int | None = None,
    preserve_explicit_hashes: bool = False,
) -> dict:
    updated = 0
    skipped = 0
    q = session.query(Catalog).order_by(Catalog.id.asc())
    if catalog_ids is None:
        q = apply_catalog_id_scope(q, Catalog.id)
    else:
        q = q.filter(Catalog.id.in_(catalog_ids))
    if limit is not None:
        q = q.limit(limit)

    for c in q:
        if not c.content:
            skipped += 1
            continue
        if _normalize_catalog_hashes_for_catalog(
            session,
            c,
            preserve_explicit_hashes=preserve_explicit_hashes,
        ):
            updated += 1

    return {"updated": updated, "skipped": skipped}


def backfill(limit: int | None = None) -> dict:
    """
    Backfill content_hash + source hashes for existing rows.

    Safe defaults:
    - If a catalog already has a derived value (summary/topics) but no source hash,
      we assume it was generated from the then-current content and mark it fresh.
      Users can still force-regenerate if needed.
    """
    with db_session() as session:
        counts = normalize_catalog_hashes(session, limit=limit)

        session.commit()

    return {"status": "ok", **counts}


def main() -> int:
    logging.basicConfig(level=logging.INFO)
    logger.info("catalog_hash_backfill_complete payload=%s", backfill())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

import logging

from pipeline.content_hash import compute_content_hash
from pipeline.db_session import db_session
from pipeline.models import Catalog

logging.basicConfig(level=logging.INFO)
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
        if limit:
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

            if c.summary and not c.summary_source_hash and content_hash:
                c.summary_source_hash = content_hash
                changed = True

            if c.topics is not None and not c.topics_source_hash and content_hash:
                c.topics_source_hash = content_hash
                changed = True

            if changed:
                updated += 1

        session.commit()

    return {"status": "ok", "updated": updated, "skipped": skipped}


if __name__ == "__main__":
    print(backfill())


import importlib

from pipeline.models import Catalog


def test_backfill_limit_zero_does_not_process_all_rows(db_session):
    module = importlib.import_module("pipeline.backfill_catalog_hashes")

    db_session.add_all(
        [
            Catalog(filename="a.pdf", url_hash="limit-zero-a", content="Agenda A"),
            Catalog(filename="b.pdf", url_hash="limit-zero-b", content="Agenda B"),
        ]
    )
    db_session.commit()

    counts = module.backfill(limit=0)

    assert counts["updated"] == 0
    assert counts["skipped"] == 0
    refreshed = db_session.query(Catalog).filter(Catalog.url_hash.in_(["limit-zero-a", "limit-zero-b"])).all()
    assert all(row.content_hash is None for row in refreshed)

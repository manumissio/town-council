import sys
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

# Mock heavy dependency before importing api.main
sys.modules["llama_cpp"] = MagicMock()

from api.main import app
from pipeline.content_hash import compute_content_hash


client = TestClient(app)
VALID_KEY = "dev_secret_key_change_me"


def test_topics_endpoint_returns_stale_when_hash_mismatches(mocker):
    from api.main import get_db

    catalog = MagicMock(
        id=1,
        content=(
            "City council meeting discussed budget updates, transportation allocations, housing projects, "
            "public safety staffing, and adopted multiple motions after extended public comment."
        ),
        topics=["Old", "Topics"],
        content_hash="newhash",
        topics_source_hash="oldhash",
    )

    db = MagicMock()
    db.get.return_value = catalog

    def _mock_get_db():
        yield db

    app.dependency_overrides[get_db] = _mock_get_db
    delay = mocker.patch("api.main.generate_topics_task.delay")
    try:
        resp = client.post("/topics/1", headers={"X-API-Key": VALID_KEY})
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["status"] == "stale"
        assert payload["topics"] == ["Old", "Topics"]
        delay.assert_not_called()
    finally:
        del app.dependency_overrides[get_db]


def test_topic_worker_sets_topics_source_hash(db_session, mocker):
    """
    Contract: when topics are generated, topics_source_hash should match the current content_hash.
    """
    from pipeline.models import Catalog
    from pipeline.topic_worker import run_topic_tagger

    c1 = Catalog(url="u1", url_hash="h1", location="p1", filename="f1", content="Hello world")
    c2 = Catalog(url="u2", url_hash="h2", location="p2", filename="f2", content="Hello council zoning")
    db_session.add_all([c1, c2])
    db_session.commit()

    reindex_spy = mocker.patch(
        "pipeline.indexer.reindex_catalogs",
        return_value={"catalogs_considered": 2, "catalogs_reindexed": 2, "catalogs_failed": 0},
    )

    run_topic_tagger()

    rows = db_session.query(Catalog).order_by(Catalog.id.asc()).all()
    assert len(rows) == 2
    for r in rows:
        assert r.content_hash == compute_content_hash(r.content)
        assert r.topics_source_hash == r.content_hash
    reindex_spy.assert_called_once_with({c1.id, c2.id})


def test_select_catalog_ids_for_topic_hydration_only_returns_missing_or_stale(db_session):
    from pipeline.models import Catalog, Document, Event, Place
    from pipeline.topic_worker import select_catalog_ids_for_topic_hydration

    place = Place(
        name="sample",
        state="CA",
        ocd_division_id="ocd-division/country:us/state:ca/place:sample",
        crawler_name="sample",
    )
    db_session.add(place)
    db_session.flush()
    event = Event(place_id=place.id, ocd_division_id=place.ocd_division_id, name="Sample Council")
    db_session.add(event)
    db_session.flush()

    fresh_content = "Council discussed housing and transit policy."
    fresh_hash = compute_content_hash(fresh_content)
    fresh_catalog = Catalog(
        url="fresh",
        url_hash="fresh",
        location="/tmp/fresh.pdf",
        filename="fresh.pdf",
        content=fresh_content,
        content_hash=fresh_hash,
        topics=["Housing"],
        topics_source_hash=fresh_hash,
    )
    stale_catalog = Catalog(
        url="stale",
        url_hash="stale",
        location="/tmp/stale.pdf",
        filename="stale.pdf",
        content="Old agenda now mentions zoning and budgets.",
        content_hash="new-hash",
        topics=["Old"],
        topics_source_hash="old-hash",
    )
    missing_catalog = Catalog(
        url="missing",
        url_hash="missing",
        location="/tmp/missing.pdf",
        filename="missing.pdf",
        content="Transit and housing updates for the city council.",
        content_hash=compute_content_hash("Transit and housing updates for the city council."),
        topics=None,
        topics_source_hash=None,
    )
    db_session.add_all([fresh_catalog, stale_catalog, missing_catalog])
    db_session.flush()
    for catalog in (fresh_catalog, stale_catalog, missing_catalog):
        db_session.add(
            Document(
                place_id=place.id,
                event_id=event.id,
                catalog_id=catalog.id,
                url=f"https://example.com/{catalog.id}",
            )
        )
    db_session.commit()

    selected = select_catalog_ids_for_topic_hydration(db_session)

    assert stale_catalog.id in selected
    assert missing_catalog.id in selected
    assert fresh_catalog.id not in selected


def test_run_topic_hydration_backfill_reuses_single_catalog_task(mocker):
    from pipeline.topic_worker import run_topic_hydration_backfill

    task_run = mocker.patch(
        "pipeline.enrichment_tasks.generate_topics_task.run",
        side_effect=[
            {"status": "complete", "topics": ["Housing"]},
            {"status": "cached", "topics": ["Transit"]},
        ],
    )

    counts = run_topic_hydration_backfill(catalog_ids=[101, 202])

    assert counts["selected"] == 2
    assert counts["complete"] == 1
    assert counts["cached"] == 1
    assert counts["error"] == 0
    assert task_run.call_args_list[0].kwargs["force"] is True
    assert task_run.call_args_list[0].kwargs["max_corpus_docs"] == 600

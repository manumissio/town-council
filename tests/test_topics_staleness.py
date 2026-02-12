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


def test_topic_worker_sets_topics_source_hash(db_session):
    """
    Contract: when topics are generated, topics_source_hash should match the current content_hash.
    """
    from pipeline.models import Catalog
    from pipeline.topic_worker import run_topic_tagger

    c1 = Catalog(url="u1", url_hash="h1", location="p1", filename="f1", content="Hello world")
    c2 = Catalog(url="u2", url_hash="h2", location="p2", filename="f2", content="Hello council zoning")
    db_session.add_all([c1, c2])
    db_session.commit()

    run_topic_tagger()

    rows = db_session.query(Catalog).order_by(Catalog.id.asc()).all()
    assert len(rows) == 2
    for r in rows:
        assert r.content_hash == compute_content_hash(r.content)
        assert r.topics_source_hash == r.content_hash

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from api.main import app, get_db
from pipeline.semantic_index import SemanticCandidate

VALID_KEY = "dev_secret_key_change_me"


class _Backend:
    def __init__(self, candidates):
        self.candidates = candidates

    def query(self, _q, _k):
        return list(self.candidates)


def test_semantic_search_success_with_filters(mocker):
    db = MagicMock()
    app.dependency_overrides[get_db] = lambda: db
    mocker.patch("api.main.SEMANTIC_ENABLED", True)
    mocker.patch(
        "api.main.get_semantic_backend",
        return_value=_Backend(
            [
                SemanticCandidate(row_id=1, score=0.9, metadata={"result_type": "meeting", "db_id": 10, "catalog_id": 101, "city": "ca_cupertino", "meeting_category": "Regular", "organization": "City Council", "date": "2025-01-01"}),
                SemanticCandidate(row_id=2, score=0.8, metadata={"result_type": "meeting", "db_id": 11, "catalog_id": 102, "city": "ca_berkeley", "meeting_category": "Regular", "organization": "City Council", "date": "2025-01-01"}),
            ]
        ),
    )
    mocker.patch("api.main._hydrate_meeting_hits", return_value=[{"id": "doc_10", "db_id": 10, "result_type": "meeting", "event_name": "Cupertino Meeting", "semantic_score": 0.9}])
    mocker.patch("api.main._hydrate_agenda_hits", return_value=[])
    client = TestClient(app)
    try:
        resp = client.get("/search/semantic?q=zoning&city=cupertino", headers={"X-API-Key": VALID_KEY})
        assert resp.status_code == 200
        data = resp.json()
        assert data["estimatedTotalHits"] == 1
        assert data["hits"][0]["id"] == "doc_10"
    finally:
        del app.dependency_overrides[get_db]


def test_semantic_search_missing_artifacts_returns_503(mocker):
    db = MagicMock()
    app.dependency_overrides[get_db] = lambda: db
    mocker.patch("api.main.SEMANTIC_ENABLED", True)

    class _Missing:
        def query(self, _q, _k):
            raise FileNotFoundError("missing")

    mocker.patch("api.main.get_semantic_backend", return_value=_Missing())
    client = TestClient(app)
    try:
        resp = client.get("/search/semantic?q=zoning", headers={"X-API-Key": VALID_KEY})
        assert resp.status_code == 503
        assert "reindex_semantic.py" in resp.json()["detail"]
    finally:
        del app.dependency_overrides[get_db]

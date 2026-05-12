from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from semantic_service.main import app, get_db
from pipeline.semantic_index import SemanticCandidate

VALID_KEY = "dev_secret_key_change_me"


class _AdaptiveBackend:
    def health(self):
        return {"status": "ok", "engine": "faiss"}

    def query(self, _q, k):
        rows = []
        # Top 200 are wrong city; only later rows satisfy city filter.
        wrong = min(k, 200)
        for i in range(wrong):
            rows.append(
                SemanticCandidate(
                    row_id=i,
                    score=1.0 - (i * 0.001),
                    metadata={
                        "result_type": "meeting",
                        "db_id": 1000 + i,
                        "catalog_id": 1000 + i,
                        "city": "ca_berkeley",
                        "meeting_category": "Regular",
                        "organization": "City Council",
                        "date": "2025-01-01",
                    },
                )
            )
        if k > 200:
            for i in range(min(k - 200, 30)):
                rows.append(
                    SemanticCandidate(
                        row_id=10000 + i,
                        score=0.5 - (i * 0.001),
                        metadata={
                            "result_type": "meeting",
                            "db_id": 5000 + i,
                            "catalog_id": 5000 + i,
                            "city": "ca_cupertino",
                            "meeting_category": "Regular",
                            "organization": "City Council",
                            "date": "2025-01-01",
                        },
                    )
                )
        return rows


class _MaxCapBackend:
    def __init__(self):
        self.calls = []

    def health(self):
        return {"status": "ok", "engine": "faiss"}

    def query(self, _q, k):
        self.calls.append(k)
        return [
            SemanticCandidate(
                row_id=1,
                score=0.9,
                metadata={
                    "result_type": "meeting",
                    "db_id": 100,
                    "catalog_id": 100,
                    "city": "ca_berkeley",
                    "meeting_category": "Regular",
                    "organization": "City Council",
                    "date": "2025-01-01",
                },
            )
        ]


def test_semantic_search_expands_top_k_until_filtered_results_exist(mocker):
    db = MagicMock()
    app.dependency_overrides[get_db] = lambda: db
    mocker.patch("semantic_service.main.SEMANTIC_ENABLED", True)
    mocker.patch("semantic_service.main.SEMANTIC_BASE_TOP_K", 200)
    mocker.patch("semantic_service.main.SEMANTIC_MAX_TOP_K", 1000)
    mocker.patch("semantic_service.main.SEMANTIC_FILTER_EXPANSION_FACTOR", 4)
    mocker.patch("semantic_service.main.get_semantic_backend", return_value=_AdaptiveBackend())
    mocker.patch(
        "semantic_service.main._hydrate_meeting_hits",
        side_effect=lambda _db, candidates: [
            {"id": f"doc_{c.metadata['db_id']}", "db_id": c.metadata["db_id"], "result_type": "meeting", "event_name": "Meeting"}
            for c in candidates
        ],
    )
    mocker.patch("semantic_service.main._hydrate_agenda_hits", return_value=[])
    client = TestClient(app)
    try:
        resp = client.get("/search/semantic?q=zoning&city=cupertino&limit=20", headers={"X-API-Key": VALID_KEY})
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["semantic_diagnostics"]["expansion_steps"] >= 1
        assert len(payload["hits"]) > 0
    finally:
        del app.dependency_overrides[get_db]


def test_semantic_search_stops_expansion_at_max_top_k(mocker):
    db = MagicMock()
    app.dependency_overrides[get_db] = lambda: db
    backend = _MaxCapBackend()
    mocker.patch("semantic_service.main.SEMANTIC_ENABLED", True)
    mocker.patch("semantic_service.main.SEMANTIC_BASE_TOP_K", 2)
    mocker.patch("semantic_service.main.SEMANTIC_MAX_TOP_K", 4)
    mocker.patch("semantic_service.main.SEMANTIC_FILTER_EXPANSION_FACTOR", 1)
    mocker.patch("semantic_service.main.get_semantic_backend", return_value=backend)
    mocker.patch("semantic_service.main._hydrate_meeting_hits", return_value=[])
    mocker.patch("semantic_service.main._hydrate_agenda_hits", return_value=[])
    client = TestClient(app)
    try:
        resp = client.get("/search/semantic?q=zoning&city=cupertino&limit=10", headers={"X-API-Key": VALID_KEY})
        assert resp.status_code == 200
        payload = resp.json()
        assert backend.calls == [4]
        assert payload["semantic_diagnostics"]["k_used"] == 4
        assert payload["semantic_diagnostics"]["expansion_steps"] == 0
        assert payload["semantic_diagnostics"]["filtered_candidates"] == 0
    finally:
        del app.dependency_overrides[get_db]

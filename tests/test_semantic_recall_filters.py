from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from api.main import app, get_db
from pipeline.semantic_index import SemanticCandidate

VALID_KEY = "dev_secret_key_change_me"


class _AdaptiveBackend:
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


def test_semantic_search_expands_top_k_until_filtered_results_exist(mocker):
    db = MagicMock()
    app.dependency_overrides[get_db] = lambda: db
    mocker.patch("api.main.SEMANTIC_ENABLED", True)
    mocker.patch("api.main.SEMANTIC_BASE_TOP_K", 200)
    mocker.patch("api.main.SEMANTIC_MAX_TOP_K", 1000)
    mocker.patch("api.main.SEMANTIC_FILTER_EXPANSION_FACTOR", 4)
    mocker.patch("api.main.get_semantic_backend", return_value=_AdaptiveBackend())
    mocker.patch(
        "api.main._hydrate_meeting_hits",
        side_effect=lambda _db, candidates: [
            {"id": f"doc_{c.metadata['db_id']}", "db_id": c.metadata["db_id"], "result_type": "meeting", "event_name": "Meeting"}
            for c in candidates
        ],
    )
    mocker.patch("api.main._hydrate_agenda_hits", return_value=[])
    client = TestClient(app)
    try:
        resp = client.get("/search/semantic?q=zoning&city=cupertino&limit=20", headers={"X-API-Key": VALID_KEY})
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["semantic_diagnostics"]["expansion_steps"] >= 1
        assert len(payload["hits"]) > 0
    finally:
        del app.dependency_overrides[get_db]

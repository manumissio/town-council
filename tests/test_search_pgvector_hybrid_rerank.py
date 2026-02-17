from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from api.main import app, get_db
from pipeline.semantic_index import SemanticCandidate

VALID_KEY = "dev_secret_key_change_me"


class _PgBackend:
    def rerank_candidates(self, _db, _query, lexical_hits, top_k):
        # Return only the highest-priority lexical meeting as semantic winner.
        first = lexical_hits[0]
        return [
            SemanticCandidate(
                row_id=0,
                score=0.92,
                metadata={
                    "result_type": "meeting",
                    "db_id": first["db_id"],
                    "catalog_id": first["catalog_id"],
                    "event_id": first["event_id"],
                    "city": first["city"],
                    "meeting_category": first["meeting_category"],
                    "organization": first["organization"],
                    "date": first["date"],
                },
            )
        ]

    def health(self):
        return {"status": "ok", "engine": "pgvector"}


def test_semantic_search_pgvector_hybrid_rerank_path(mocker):
    db = MagicMock()
    app.dependency_overrides[get_db] = lambda: db

    mocker.patch("api.main.SEMANTIC_ENABLED", True)
    mocker.patch("api.main.SEMANTIC_BACKEND", "pgvector")
    mocker.patch("api.main.get_semantic_backend", return_value=_PgBackend())

    meili_index = MagicMock()
    meili_index.search.return_value = {
        "hits": [
            {
                "id": "doc_10",
                "db_id": 10,
                "event_id": 3,
                "catalog_id": 101,
                "result_type": "meeting",
                "city": "ca_cupertino",
                "meeting_category": "Regular",
                "organization": "City Council",
                "date": "2025-01-01",
            }
        ]
    }
    mocker.patch("api.main.client.index", return_value=meili_index)
    mocker.patch(
        "api.main._hydrate_meeting_hits",
        return_value=[{"id": "doc_10", "db_id": 10, "result_type": "meeting", "event_name": "Meeting"}],
    )
    mocker.patch("api.main._hydrate_agenda_hits", return_value=[])

    client = TestClient(app)
    try:
        resp = client.get("/search/semantic?q=zoning&limit=20", headers={"X-API-Key": VALID_KEY})
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["hits"][0]["id"] == "doc_10"
        assert payload["semantic_diagnostics"]["engine"] == "pgvector"
        assert payload["estimatedTotalHits"] == 1
    finally:
        del app.dependency_overrides[get_db]

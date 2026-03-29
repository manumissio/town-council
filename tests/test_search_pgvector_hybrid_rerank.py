from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from semantic_service.main import app, get_db
from pipeline.semantic_index import SemanticCandidate, SemanticRerankResult

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

    def rerank_candidates_with_diagnostics(self, db, query, lexical_hits, top_k):
        candidates = self.rerank_candidates(db, query, lexical_hits, top_k)
        return SemanticRerankResult(
            candidates=candidates,
            diagnostics={
                "retrieval_mode": "hybrid_pgvector",
                "result_scope": "meeting_hybrid",
                "hybrid_rerank_applied": True,
                "degraded_to_lexical": False,
                "skipped_reason": None,
                "lexical_candidates": len(lexical_hits),
                "eligible_meeting_candidates": len(lexical_hits),
                "candidate_limit_applied": len(lexical_hits),
                "fresh_embeddings": len(candidates),
                "missing_embeddings": 0,
                "stale_embeddings": 0,
                "lexical_fallback_candidates": 0,
            },
        )

    def health(self):
        return {"status": "ok", "engine": "pgvector"}


def test_semantic_search_pgvector_hybrid_rerank_path(mocker):
    db = MagicMock()
    app.dependency_overrides[get_db] = lambda: db

    mocker.patch("semantic_service.main.SEMANTIC_ENABLED", True)
    mocker.patch("semantic_service.main.SEMANTIC_BACKEND", "pgvector")
    mocker.patch("semantic_service.main.get_semantic_backend", return_value=_PgBackend())

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
    mocker.patch("semantic_service.main.client.index", return_value=meili_index)
    mocker.patch(
        "semantic_service.main._hydrate_meeting_hits",
        return_value=[{"id": "doc_10", "db_id": 10, "result_type": "meeting", "event_name": "Meeting"}],
    )
    mocker.patch("semantic_service.main._hydrate_agenda_hits", return_value=[])

    client = TestClient(app)
    try:
        resp = client.get("/search/semantic?q=zoning&limit=20", headers={"X-API-Key": VALID_KEY})
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["hits"][0]["id"] == "doc_10"
        assert payload["semantic_diagnostics"]["engine"] == "pgvector"
        assert payload["estimatedTotalHits"] == 1
        assert payload["semantic_diagnostics"]["retrieval_mode"] == "hybrid_pgvector"
        assert payload["semantic_diagnostics"]["result_scope"] == "meeting_hybrid"
        assert payload["semantic_diagnostics"]["hybrid_rerank_applied"] is True
    finally:
        del app.dependency_overrides[get_db]


class _FallbackPgBackend:
    def rerank_candidates_with_diagnostics(self, _db, _query, lexical_hits, top_k):
        _ = top_k
        return SemanticRerankResult(
            candidates=[],
            diagnostics={
                "retrieval_mode": "hybrid_pgvector",
                "result_scope": "meeting_hybrid",
                "hybrid_rerank_applied": False,
                "degraded_to_lexical": True,
                "skipped_reason": "missing_embeddings",
                "lexical_candidates": len(lexical_hits),
                "eligible_meeting_candidates": len(lexical_hits),
                "candidate_limit_applied": len(lexical_hits),
                "fresh_embeddings": 0,
                "missing_embeddings": len(lexical_hits),
                "stale_embeddings": 0,
                "lexical_fallback_candidates": 0,
            },
        )

    def health(self):
        return {"status": "ok", "engine": "pgvector"}


def test_semantic_search_pgvector_falls_back_to_lexical_when_embeddings_missing(mocker):
    db = MagicMock()
    app.dependency_overrides[get_db] = lambda: db

    mocker.patch("semantic_service.main.SEMANTIC_ENABLED", True)
    mocker.patch("semantic_service.main.SEMANTIC_BACKEND", "pgvector")
    mocker.patch("semantic_service.main.get_semantic_backend", return_value=_FallbackPgBackend())

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
    mocker.patch("semantic_service.main.client.index", return_value=meili_index)
    mocker.patch(
        "semantic_service.main._hydrate_meeting_hits",
        return_value=[{"id": "doc_10", "db_id": 10, "result_type": "meeting", "event_name": "Meeting"}],
    )
    mocker.patch("semantic_service.main._hydrate_agenda_hits", return_value=[])

    client = TestClient(app)
    try:
        resp = client.get("/search/semantic?q=zoning&limit=20", headers={"X-API-Key": VALID_KEY})
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["hits"][0]["id"] == "doc_10"
        assert payload["semantic_diagnostics"]["degraded_to_lexical"] is True
        assert payload["semantic_diagnostics"]["skipped_reason"] == "missing_embeddings"
        assert payload["semantic_diagnostics"]["lexical_fallback_candidates"] == 1
    finally:
        del app.dependency_overrides[get_db]

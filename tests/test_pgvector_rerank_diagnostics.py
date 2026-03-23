from unittest.mock import MagicMock

import numpy as np

from pipeline.semantic_index import (
    PgvectorSemanticBackend,
    catalog_semantic_source_hash,
)


def _candidate_hit():
    return [
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


def test_pgvector_rerank_reports_missing_embeddings(mocker):
    backend = PgvectorSemanticBackend()
    mocker.patch.object(backend, "_encode", return_value=np.ones((1, 4), dtype=np.float32))

    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = [(101, "Budget and zoning update")]
    db.execute.return_value.mappings.return_value = []

    result = backend.rerank_candidates_with_diagnostics(db, "zoning", _candidate_hit(), top_k=5)

    assert result.candidates == []
    assert result.diagnostics["degraded_to_lexical"] is True
    assert result.diagnostics["skipped_reason"] == "missing_embeddings"
    assert result.diagnostics["eligible_meeting_candidates"] == 1
    assert result.diagnostics["fresh_embeddings"] == 0
    assert result.diagnostics["missing_embeddings"] == 1
    assert result.diagnostics["stale_embeddings"] == 0


def test_pgvector_rerank_reports_fresh_embedding_coverage(mocker):
    backend = PgvectorSemanticBackend()
    mocker.patch.object(backend, "_encode", return_value=np.ones((1, 4), dtype=np.float32))

    summary = "Budget and zoning update"
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = [(101, summary)]
    db.execute.return_value.mappings.return_value = [
        {
            "catalog_id": 101,
            "source_hash": catalog_semantic_source_hash(summary),
            "score": 0.91,
        }
    ]

    result = backend.rerank_candidates_with_diagnostics(db, "zoning", _candidate_hit(), top_k=5)

    assert len(result.candidates) == 1
    assert result.candidates[0].metadata["catalog_id"] == 101
    assert result.diagnostics["hybrid_rerank_applied"] is True
    assert result.diagnostics["degraded_to_lexical"] is False
    assert result.diagnostics["fresh_embeddings"] == 1
    assert result.diagnostics["missing_embeddings"] == 0
    assert result.diagnostics["stale_embeddings"] == 0

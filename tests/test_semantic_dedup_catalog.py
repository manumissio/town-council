from api.main import _dedupe_semantic_candidates
from pipeline.semantic_index import SemanticCandidate


def test_semantic_dedup_uses_best_score_per_catalog():
    candidates = [
        SemanticCandidate(row_id=1, score=0.70, metadata={"result_type": "meeting", "catalog_id": 10, "db_id": 1}),
        SemanticCandidate(row_id=2, score=0.95, metadata={"result_type": "meeting", "catalog_id": 10, "db_id": 1}),
        SemanticCandidate(row_id=3, score=0.80, metadata={"result_type": "meeting", "catalog_id": 11, "db_id": 2}),
    ]
    deduped = _dedupe_semantic_candidates(candidates)
    assert len(deduped) == 2
    assert deduped[0].metadata["catalog_id"] == 10
    assert deduped[0].score == 0.95

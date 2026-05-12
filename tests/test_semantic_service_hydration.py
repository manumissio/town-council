from types import SimpleNamespace
from unittest.mock import MagicMock

from pipeline.semantic_index import SemanticCandidate
from semantic_service.hydration import (
    SemanticResponseTiming,
    build_semantic_search_response,
    hydrate_meeting_hits,
)
from semantic_service.retrieval import SemanticRetrievalResult


def test_semantic_response_preserves_mixed_candidate_order_and_drops_missing_hits():
    retrieval_result = SemanticRetrievalResult(
        deduped=[
            _candidate("meeting", 10, 100, 0.91),
            _candidate("agenda_item", 20, 100, 0.82),
            _candidate("meeting", 30, 300, 0.73),
        ],
        raw_count=4,
        filtered_count=3,
        k_used=200,
        expansion_steps=1,
        diagnostics_extra={"retrieval_mode": "vector_direct"},
    )

    response = build_semantic_search_response(
        db=MagicMock(),
        retrieval_result=retrieval_result,
        limit=3,
        offset=0,
        timing=SemanticResponseTiming(elapsed_ms=12.5, engine="faiss"),
        hydrate_meetings=lambda _db, _candidates: [
            {"db_id": 10, "id": "doc_10", "result_type": "meeting"},
            {"db_id": 30, "id": "doc_30", "result_type": "meeting"},
        ],
        hydrate_agenda_items=lambda _db, _candidates: [],
    )

    assert [hit["id"] for hit in response["hits"]] == ["doc_10", "doc_30"]
    assert response["estimatedTotalHits"] == 3
    assert response["semantic_diagnostics"]["dedup_candidates"] == 3
    assert response["semantic_diagnostics"]["latency_ms"] == 12.5
    assert response["semantic_diagnostics"]["engine"] == "faiss"


def test_semantic_response_applies_offset_after_dedupe_before_hydration():
    retrieval_result = SemanticRetrievalResult(
        deduped=[
            _candidate("meeting", 10, 100, 0.91),
            _candidate("meeting", 20, 200, 0.82),
        ],
        raw_count=2,
        filtered_count=2,
        k_used=200,
        expansion_steps=0,
        diagnostics_extra={},
    )

    response = build_semantic_search_response(
        db=MagicMock(),
        retrieval_result=retrieval_result,
        limit=1,
        offset=1,
        timing=SemanticResponseTiming(elapsed_ms=1.0, engine=None),
        hydrate_meetings=lambda _db, candidates: [
            {"db_id": candidates[0].metadata["db_id"], "id": f"doc_{candidates[0].metadata['db_id']}"}
        ],
        hydrate_agenda_items=lambda _db, _candidates: [],
    )

    assert [hit["id"] for hit in response["hits"]] == ["doc_20"]
    assert response["estimatedTotalHits"] == 2
    assert response["limit"] == 1
    assert response["offset"] == 1


def test_hydrate_meeting_hits_rounds_semantic_score_to_six_decimals():
    db = MagicMock()
    query = db.query.return_value
    query.join.return_value = query
    query.outerjoin.return_value = query
    query.filter.return_value = query
    query.all.return_value = [(_doc(), _catalog(), _event(), _place(), None)]

    hits = hydrate_meeting_hits(db, [_candidate("meeting", 10, 100, 0.123456789)])

    assert hits[0]["semantic_score"] == 0.123457
    assert hits[0]["id"] == "doc_10"
    assert hits[0]["organization"] == "City Council"


def _candidate(result_type: str, db_id: int, catalog_id: int, score: float) -> SemanticCandidate:
    return SemanticCandidate(
        row_id=db_id,
        score=score,
        metadata={"result_type": result_type, "db_id": db_id, "catalog_id": catalog_id},
    )


def _doc() -> SimpleNamespace:
    return SimpleNamespace(id=10, catalog_id=100, event_id=1, place_id=1)


def _catalog() -> SimpleNamespace:
    return SimpleNamespace(
        id=100,
        filename="agenda.pdf",
        url="https://example.test/agenda.pdf",
        content="Meeting content",
        summary="Summary",
        summary_extractive=None,
        topics=["housing"],
        related_ids=[],
        content_hash="abc",
        summary_source_hash="abc",
        topics_source_hash="abc",
    )


def _event() -> SimpleNamespace:
    return SimpleNamespace(ocd_id="ocd-1", name="Council Meeting", meeting_type=None, record_date=None)


def _place() -> SimpleNamespace:
    return SimpleNamespace(display_name="Cupertino", name="cupertino", state="CA")

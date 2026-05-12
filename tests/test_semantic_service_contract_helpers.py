from pipeline.semantic_index import SemanticCandidate
from semantic_service import candidates
from semantic_service.main import _lexical_hit_to_candidate as facade_lexical_hit_to_candidate


def test_semantic_main_keeps_lexical_candidate_compatibility_seam():
    assert facade_lexical_hit_to_candidate is candidates.lexical_hit_to_candidate


def test_semantic_lexical_meeting_candidate_rejects_malformed_doc_id():
    candidate = candidates.lexical_hit_to_candidate(
        {"id": "doc_not-an-int", "catalog_id": 12, "result_type": "meeting"},
        0,
    )

    assert candidate is None


def test_semantic_lexical_agenda_candidate_rejects_malformed_item_id():
    candidate = candidates.lexical_hit_to_candidate({"id": "item_bad", "result_type": "agenda_item"}, 0)

    assert candidate is None


def test_semantic_lexical_candidate_preserves_meeting_metadata_defaults():
    candidate = candidates.lexical_hit_to_candidate({"id": "doc_7", "catalog_id": 12, "result_type": "meeting"}, 2)

    assert candidate is not None
    assert candidate.row_id == 2
    assert candidate.score == -3.0
    assert candidate.metadata == {
        "result_type": "meeting",
        "catalog_id": 12,
        "db_id": 7,
        "event_id": None,
        "city": "",
        "meeting_category": "Other",
        "organization": "City Council",
        "date": None,
        "source_type": "lexical_fallback",
    }


def test_semantic_filter_matching_preserves_case_insensitive_boundaries():
    filters = {
        "include_agenda_items": True,
        "city": "Cupertino",
        "meeting_type": "Regular",
        "org": "City Council",
        "date_from": "2026-01-01",
        "date_to": "2026-01-31",
    }
    metadata = {
        "result_type": "agenda_item",
        "city": "cupertino",
        "meeting_category": "regular",
        "organization": "city council",
        "date": "2026-01-31",
    }

    assert candidates.semantic_candidate_matches_filters(metadata, filters)


def test_semantic_filter_matching_excludes_agenda_items_by_default():
    assert not candidates.semantic_candidate_matches_filters(
        {"result_type": "agenda_item", "date": "2026-01-10"},
        {"include_agenda_items": False},
    )


def test_semantic_filter_matching_rejects_out_of_range_dates():
    assert not candidates.semantic_candidate_matches_filters(
        {"result_type": "meeting", "date": "2025-12-31"},
        {"include_agenda_items": False, "date_from": "2026-01-01"},
    )


def test_semantic_dedupe_keeps_highest_score_per_result_key():
    semantic_candidates = [
        SemanticCandidate(row_id=1, score=0.2, metadata={"result_type": "meeting", "catalog_id": 10, "db_id": 1}),
        SemanticCandidate(row_id=2, score=0.9, metadata={"result_type": "meeting", "catalog_id": 10, "db_id": 2}),
        SemanticCandidate(row_id=3, score=0.8, metadata={"result_type": "agenda_item", "db_id": 5}),
    ]

    deduped = candidates.dedupe_semantic_candidates(semantic_candidates)

    assert [candidate.row_id for candidate in deduped] == [2, 3]

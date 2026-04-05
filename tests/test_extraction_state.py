from types import SimpleNamespace

from pipeline.extraction_state import mark_extraction_complete, mark_extraction_failure


def test_mark_extraction_complete_sets_shared_success_fields():
    catalog = SimpleNamespace(
        content_hash=None,
        extraction_status="pending",
        extraction_attempt_count=0,
        extraction_attempted_at=None,
        extraction_error="old",
    )

    mark_extraction_complete(catalog, "hash-123")

    assert catalog.content_hash == "hash-123"
    assert catalog.extraction_status == "complete"
    assert catalog.extraction_attempt_count == 1
    assert catalog.extraction_attempted_at is not None
    assert getattr(catalog.extraction_attempted_at, "tzinfo", None) is not None
    assert catalog.extraction_error is None


def test_mark_extraction_failure_transitions_to_terminal_after_threshold():
    catalog = SimpleNamespace(
        extraction_attempt_count=2,
        extraction_attempted_at=None,
        extraction_error=None,
        extraction_status="pending",
    )

    mark_extraction_failure(catalog, "x" * 600)

    assert catalog.extraction_attempt_count == 3
    assert catalog.extraction_status == "failed_terminal"
    assert catalog.extraction_attempted_at is not None
    assert getattr(catalog.extraction_attempted_at, "tzinfo", None) is not None
    assert len(catalog.extraction_error) == 500

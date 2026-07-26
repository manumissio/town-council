from datetime import UTC, datetime
import logging

from pipeline.run_pipeline_onboarding import parse_onboarding_started_at


def test_onboarding_scope_parser_returns_aware_utc() -> None:
    parsed_at = parse_onboarding_started_at(
        "2026-07-25T16:30:00Z",
        logger=logging.getLogger(__name__),
    )

    assert parsed_at == datetime(2026, 7, 25, 16, 30, tzinfo=UTC)


def test_onboarding_scope_parser_preserves_invalid_input_fallback(caplog) -> None:
    with caplog.at_level(logging.WARNING):
        parsed_at = parse_onboarding_started_at(
            "not-a-timestamp",
            logger=logging.getLogger(__name__),
        )

    assert parsed_at is None
    assert "falling back to city-wide scope" in caplog.text

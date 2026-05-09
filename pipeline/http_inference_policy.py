from __future__ import annotations

from typing import Final

from pipeline.inference_provider_contract import (
    OPERATION_EXTRACT_AGENDA,
    OPERATION_GENERATE_JSON,
    OPERATION_GENERATE_TOPICS,
    OPERATION_SEGMENT_AGENDA,
    OPERATION_SUMMARIZE_AGENDA_ITEMS,
    OPERATION_SUMMARIZE_TEXT,
)


HTTP_PROVIDER_NAME: Final = "http"
MINIMUM_HTTP_TIMEOUT_SECONDS: Final = 5
HEALTH_CHECK_TIMEOUT_SECONDS: Final = 5
CONSERVATIVE_HTTP_PROFILE: Final = "conservative"


def timeout_for_operation(
    operation: str,
    *,
    default_timeout_seconds: int,
    segment_timeout_seconds: int,
    summary_timeout_seconds: int,
    topics_timeout_seconds: int,
) -> int:
    # Workload classes pick timeout budgets; infra profiles own concurrency.
    if operation in {OPERATION_EXTRACT_AGENDA, OPERATION_SEGMENT_AGENDA, OPERATION_GENERATE_JSON}:
        return segment_timeout_seconds
    if operation in {OPERATION_SUMMARIZE_AGENDA_ITEMS, OPERATION_SUMMARIZE_TEXT}:
        return summary_timeout_seconds
    if operation == OPERATION_GENERATE_TOPICS:
        return topics_timeout_seconds
    return default_timeout_seconds


def max_retries_for_operation(
    operation: str,
    *,
    max_retries: int,
    profile_name: str,
) -> int:
    if operation == OPERATION_EXTRACT_AGENDA:
        return 0
    if max_retries <= 0:
        return 0
    if profile_name == CONSERVATIVE_HTTP_PROFILE and operation in {
        OPERATION_SUMMARIZE_AGENDA_ITEMS,
        OPERATION_SUMMARIZE_TEXT,
        OPERATION_GENERATE_TOPICS,
    }:
        return 0
    return max_retries

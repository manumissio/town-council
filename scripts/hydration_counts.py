from __future__ import annotations

from collections.abc import Callable
from typing import Any

HydrationPayload = dict[str, Any]  # Any: operator payloads mix nested count, JSON, and status fields.
ProgressCallback = Callable[[HydrationPayload], None]

SUMMARY_COUNT_KEYS = (
    "selected",
    "complete",
    "cached",
    "stale",
    "blocked_low_signal",
    "blocked_ungrounded",
    "not_generated_yet",
    "error",
    "other",
)
STAGED_SUMMARY_COUNT_KEYS = (*SUMMARY_COUNT_KEYS, "llm_complete", "deterministic_fallback_complete")
REPAIRED_SUMMARY_COUNT_KEYS = (
    *SUMMARY_COUNT_KEYS,
    "agenda_deterministic_complete",
    "llm_complete",
    "deterministic_fallback_complete",
)
SEGMENT_COUNT_KEYS = (
    "complete",
    "empty",
    "failed",
    "timed_out",
    "other",
    "timeout_fallbacks",
    "empty_response_fallbacks",
    "llm_attempted",
    "llm_skipped_heuristic_first",
    "heuristic_complete",
    "llm_timeout_then_fallback",
)
REPAIRED_SEGMENT_COUNT_KEYS = tuple(count_name for count_name in SEGMENT_COUNT_KEYS if count_name != "timed_out")


def empty_staged_summary_counts() -> dict[str, int]:
    return {key: 0 for key in STAGED_SUMMARY_COUNT_KEYS}


def empty_repaired_summary_counts() -> dict[str, int]:
    return {key: 0 for key in REPAIRED_SUMMARY_COUNT_KEYS}


def empty_segment_counts() -> dict[str, int]:
    return {key: 0 for key in SEGMENT_COUNT_KEYS}


def empty_repaired_segment_counts() -> dict[str, int]:
    return {key: 0 for key in REPAIRED_SEGMENT_COUNT_KEYS}


def merge_counts(base_counts: dict[str, int], additional_counts: dict[str, int]) -> dict[str, int]:
    merged_counts = dict(base_counts)
    for count_name, count_value in additional_counts.items():
        merged_counts[count_name] = int(merged_counts.get(count_name, 0)) + int(count_value)
    return merged_counts


def rate_per_second(total: int, elapsed_seconds: float) -> float:
    if elapsed_seconds <= 0:
        return 0.0
    return total / elapsed_seconds

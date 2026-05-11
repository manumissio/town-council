from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from statistics import median
from typing import Any


def to_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    return text in {"1", "true", "yes", "y"}


def to_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def p95(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = max(0, int(math.ceil(0.95 * len(ordered))) - 1)
    return float(ordered[idx])


def _empty_arm_payload() -> dict[str, float | int]:
    return {
        "n": 0,
        "section_compliance_rate": 0.0,
        "fallback_rate": 0.0,
        "grounding_rate": 0.0,
        "failure_rate": 0.0,
        "summary_p95_s": 0.0,
        "segment_p95_s": 0.0,
        "partial_disclosure_rate": 0.0,
        "ttft_median_ms": 0.0,
        "ttft_p95_ms": 0.0,
        "ttft_n": 0,
        "tokens_per_sec_median": 0.0,
        "tokens_per_sec_n": 0,
        "prompt_tokens_total": 0,
        "completion_tokens_total": 0,
        "total_tokens_total": 0,
    }


def _flag_rate(rows: Sequence[Mapping[str, Any]], key: str) -> float:
    return sum(1 for row in rows if to_bool(row.get(key))) / len(rows)


def _positive_metric_values(rows: Sequence[Mapping[str, Any]], key: str) -> list[float]:
    values: list[float] = []
    for row in rows:
        value = to_float(row.get(key))
        if value > 0:
            values.append(value)
    return values


def _metric_median(values: Sequence[float]) -> float:
    return float(median(values)) if values else 0.0


def _token_total(rows: Sequence[Mapping[str, Any]], key: str) -> int:
    return sum(int(to_float(row.get(key), 0.0)) for row in rows)


def aggregate_arm(rows: Sequence[Mapping[str, Any]]) -> dict[str, float | int]:
    total = len(rows)
    if total == 0:
        return _empty_arm_payload()

    ttft_values = _positive_metric_values(rows, "ttft_ms")
    tokens_per_second_values = _positive_metric_values(rows, "tokens_per_sec")

    return {
        "n": total,
        "section_compliance_rate": _flag_rate(rows, "section_compliance_pass"),
        "fallback_rate": _flag_rate(rows, "fallback_used"),
        "grounding_rate": _flag_rate(rows, "grounding_pass"),
        "failure_rate": _flag_rate(rows, "task_failed"),
        "summary_p95_s": p95([to_float(row.get("summary_duration_s")) for row in rows]),
        "segment_p95_s": p95([to_float(row.get("segment_duration_s")) for row in rows]),
        "partial_disclosure_rate": _flag_rate(rows, "partial_coverage_disclosed"),
        "ttft_median_ms": _metric_median(ttft_values),
        "ttft_p95_ms": p95(ttft_values),
        "ttft_n": len(ttft_values),
        "tokens_per_sec_median": _metric_median(tokens_per_second_values),
        "tokens_per_sec_n": len(tokens_per_second_values),
        "prompt_tokens_total": _token_total(rows, "prompt_tokens"),
        "completion_tokens_total": _token_total(rows, "completion_tokens"),
        "total_tokens_total": _token_total(rows, "total_tokens"),
    }

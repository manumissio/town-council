from __future__ import annotations

import json
import re

from pipeline.vote_extraction_contracts import OUTCOME_SYNONYMS, VALID_OUTCOME_LABELS, VoteExtractionResult


CONFIDENCE_COERCION_ERRORS = (TypeError, ValueError)


def normalize_outcome_label(value: object) -> str:
    raw = str(value or "").strip().lower()
    if not raw:
        return "unknown"
    raw = raw.replace("-", "_")
    raw = re.sub(r"\s+", " ", raw)
    if raw in VALID_OUTCOME_LABELS:
        return raw
    if raw in OUTCOME_SYNONYMS:
        return OUTCOME_SYNONYMS[raw]
    if raw.replace(" ", "_") in VALID_OUTCOME_LABELS:
        return raw.replace(" ", "_")
    for synonym, normalized in OUTCOME_SYNONYMS.items():
        if synonym in raw:
            return normalized
    return "unknown"


def extract_first_json_object(text: str) -> str:
    value = (text or "").strip()
    if not value:
        raise ValueError("empty model output")
    first = value.find("{")
    if first < 0:
        raise ValueError("no json object start")

    depth = 0
    for index in range(first, len(value)):
        char = value[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return value[first : index + 1]
    raise ValueError("unterminated json object")


def coerce_optional_int(value: object | None) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError("boolean is not valid integer")
    if isinstance(value, int):
        coerced = value
    else:
        raw_value = str(value).strip()
        if not raw_value:
            return None
        coerced = int(raw_value)
    if coerced < 0:
        raise ValueError("vote counts must be non-negative")
    return coerced


def parse_vote_extraction_response(raw_output: str, council_size: int | None = None) -> VoteExtractionResult:
    payload_text = extract_first_json_object(raw_output)
    payload = json.loads(payload_text)
    if not isinstance(payload, dict):
        raise ValueError("vote extraction payload is not a JSON object")

    outcome_label = normalize_outcome_label(payload.get("outcome_label"))
    confidence_value = _coerced_confidence(payload.get("confidence", 0.0))
    yes_count = coerce_optional_int(payload.get("yes_count"))
    no_count = coerce_optional_int(payload.get("no_count"))
    abstain_count = coerce_optional_int(payload.get("abstain_count"))
    absent_count = coerce_optional_int(payload.get("absent_count"))
    _validate_council_size(council_size, yes_count, no_count, abstain_count, absent_count)

    return VoteExtractionResult(
        outcome_label=outcome_label,
        confidence=confidence_value,
        motion_text=_compact_optional_text(payload.get("motion_text"), limit=500),
        vote_tally_raw=_compact_optional_text(payload.get("vote_tally_raw"), limit=300),
        yes_count=yes_count,
        no_count=no_count,
        abstain_count=abstain_count,
        absent_count=absent_count,
        evidence_snippet=_compact_optional_text(payload.get("evidence_snippet"), limit=280),
    )


def _coerced_confidence(confidence: object) -> float:
    if isinstance(confidence, bool):
        return 0.0
    if not isinstance(confidence, int | float | str):
        return 0.0
    try:
        confidence_value = float(confidence)
    except CONFIDENCE_COERCION_ERRORS:
        confidence_value = 0.0
    return max(0.0, min(1.0, confidence_value))


def _validate_council_size(
    council_size: int | None,
    yes_count: int | None,
    no_count: int | None,
    abstain_count: int | None,
    absent_count: int | None,
) -> None:
    if council_size and council_size > 0:
        total = sum(v or 0 for v in (yes_count, no_count, abstain_count, absent_count))
        if total > council_size:
            raise ValueError("vote tally exceeds known council size")


def _compact_optional_text(value: object, *, limit: int) -> str | None:
    if value is None:
        return None
    return " ".join(str(value).split())[:limit] or None

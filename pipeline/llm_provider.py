from __future__ import annotations

from pipeline.http_inference_provider import HttpInferenceProvider
from pipeline.inference_provider_contract import (
    EVAL_COUNT_FIELD,
    EVAL_DURATION_FIELD,
    OPERATION_EXTRACT_AGENDA,
    OPERATION_GENERATE_JSON,
    OPERATION_GENERATE_TOPICS,
    OPERATION_SEGMENT_AGENDA,
    OPERATION_SUMMARIZE_AGENDA_ITEMS,
    OPERATION_SUMMARIZE_TEXT,
    PROMPT_EVAL_COUNT_FIELD,
    PROMPT_EVAL_DURATION_FIELD,
    RESPONSE_FIELD_NAME,
    TOTAL_DURATION_FIELD,
    InferenceProvider,
    ProviderError,
    ProviderResponseError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from pipeline.inprocess_inference_provider import InProcessLlamaProvider


__all__ = [
    "EVAL_COUNT_FIELD",
    "EVAL_DURATION_FIELD",
    "HttpInferenceProvider",
    "InferenceProvider",
    "InProcessLlamaProvider",
    "OPERATION_EXTRACT_AGENDA",
    "OPERATION_GENERATE_JSON",
    "OPERATION_GENERATE_TOPICS",
    "OPERATION_SEGMENT_AGENDA",
    "OPERATION_SUMMARIZE_AGENDA_ITEMS",
    "OPERATION_SUMMARIZE_TEXT",
    "PROMPT_EVAL_COUNT_FIELD",
    "PROMPT_EVAL_DURATION_FIELD",
    "ProviderError",
    "ProviderResponseError",
    "ProviderTimeoutError",
    "ProviderUnavailableError",
    "RESPONSE_FIELD_NAME",
    "TOTAL_DURATION_FIELD",
]

from __future__ import annotations

import requests

from pipeline.config import (
    LOCAL_AI_HTTP_BASE_URL,
    LOCAL_AI_HTTP_MAX_RETRIES,
    LOCAL_AI_HTTP_MODEL,
    LOCAL_AI_HTTP_PROFILE,
    LOCAL_AI_HTTP_TIMEOUT_SECONDS,
    LOCAL_AI_HTTP_TIMEOUT_SEGMENT_SECONDS,
    LOCAL_AI_HTTP_TIMEOUT_SUMMARY_SECONDS,
    LOCAL_AI_HTTP_TIMEOUT_TOPICS_SECONDS,
)
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
from pipeline.metrics import (
    record_provider_request,
    record_provider_retry,
    record_provider_timeout,
    record_provider_token_counts,
    record_provider_tokens_per_sec,
    record_provider_ttft,
)


__all__ = [
    "EVAL_COUNT_FIELD",
    "EVAL_DURATION_FIELD",
    "HttpInferenceProvider",
    "InferenceProvider",
    "InProcessLlamaProvider",
    "LOCAL_AI_HTTP_BASE_URL",
    "LOCAL_AI_HTTP_MAX_RETRIES",
    "LOCAL_AI_HTTP_MODEL",
    "LOCAL_AI_HTTP_PROFILE",
    "LOCAL_AI_HTTP_TIMEOUT_SECONDS",
    "LOCAL_AI_HTTP_TIMEOUT_SEGMENT_SECONDS",
    "LOCAL_AI_HTTP_TIMEOUT_SUMMARY_SECONDS",
    "LOCAL_AI_HTTP_TIMEOUT_TOPICS_SECONDS",
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
    "record_provider_request",
    "record_provider_retry",
    "record_provider_timeout",
    "record_provider_token_counts",
    "record_provider_tokens_per_sec",
    "record_provider_ttft",
    "requests",
]

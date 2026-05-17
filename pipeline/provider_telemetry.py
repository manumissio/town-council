from __future__ import annotations

import logging
from dataclasses import dataclass
from types import ModuleType

from pipeline.inference_provider_contract import (
    EVAL_COUNT_FIELD,
    EVAL_DURATION_FIELD,
    PROMPT_EVAL_COUNT_FIELD,
    PROMPT_EVAL_DURATION_FIELD,
    TOTAL_DURATION_FIELD,
)


TokenMetrics = dict[str, float | int | None]

TOKEN_METRIC_PROMPT_TOKENS = "prompt_tokens"
TOKEN_METRIC_COMPLETION_TOKENS = "completion_tokens"
TOKEN_METRIC_TOTAL_TOKENS = "total_tokens"
TOKEN_METRIC_PROMPT_EVAL_DURATION_MS = "prompt_eval_duration_ms"
TOKEN_METRIC_EVAL_DURATION_MS = "eval_duration_ms"
TOKEN_METRIC_TTFT_MS = "ttft_ms"
TOKEN_METRIC_TOKENS_PER_SEC = "tokens_per_sec"
OPENAI_USAGE_FIELD = "usage"
OPENAI_PROMPT_TOKENS_FIELD = "prompt_tokens"
OPENAI_COMPLETION_TOKENS_FIELD = "completion_tokens"
OPENAI_TOTAL_TOKENS_FIELD = "total_tokens"
NANOSECONDS_PER_MILLISECOND = 1_000_000.0
NANOSECONDS_PER_SECOND = 1_000_000_000.0


@dataclass(frozen=True)
class ProviderTelemetryIdentity:
    provider_name: str
    model_name: str
    profile_name: str
    api_name: str = ""


@dataclass(frozen=True)
class ProviderRetryTelemetry:
    operation: str
    attempt: int
    max_retries: int
    timeout_seconds: int
    error: Exception


@dataclass(frozen=True)
class ProviderAttemptTelemetry:
    operation: str
    attempt: int
    max_retries: int
    timeout_seconds: int
    outcome: str
    last_error: Exception | None
    duration_ms: float
    token_metrics: TokenMetrics


def empty_token_metrics() -> TokenMetrics:
    return {
        TOKEN_METRIC_PROMPT_TOKENS: None,
        TOKEN_METRIC_COMPLETION_TOKENS: None,
        TOKEN_METRIC_TOTAL_TOKENS: None,
        TOKEN_METRIC_PROMPT_EVAL_DURATION_MS: None,
        TOKEN_METRIC_EVAL_DURATION_MS: None,
        TOKEN_METRIC_TTFT_MS: None,
        TOKEN_METRIC_TOKENS_PER_SEC: None,
    }


def parse_token_metrics(payload: dict[str, object]) -> TokenMetrics:
    prompt_tokens = None
    completion_tokens = None
    total_tokens = None
    prompt_eval_duration_ms = None
    eval_duration_ms = None
    ttft_ms = None
    tokens_per_sec = None

    prompt_eval_count = payload.get(PROMPT_EVAL_COUNT_FIELD)
    eval_count = payload.get(EVAL_COUNT_FIELD)
    prompt_eval_duration_ns = payload.get(PROMPT_EVAL_DURATION_FIELD)
    eval_duration_ns = payload.get(EVAL_DURATION_FIELD)
    total_duration_ns = payload.get(TOTAL_DURATION_FIELD)

    if isinstance(prompt_eval_count, int):
        prompt_tokens = max(0, prompt_eval_count)
    if isinstance(eval_count, int):
        completion_tokens = max(0, eval_count)
    if prompt_tokens is not None or completion_tokens is not None:
        total_tokens = (prompt_tokens or 0) + (completion_tokens or 0)

    if isinstance(prompt_eval_duration_ns, (int, float)) and prompt_eval_duration_ns > 0:
        prompt_eval_duration_ms = float(prompt_eval_duration_ns) / NANOSECONDS_PER_MILLISECOND
        ttft_ms = prompt_eval_duration_ms
    if isinstance(eval_duration_ns, (int, float)) and eval_duration_ns > 0:
        eval_duration_ms = float(eval_duration_ns) / NANOSECONDS_PER_MILLISECOND
        eval_duration_s = float(eval_duration_ns) / NANOSECONDS_PER_SECOND
        if completion_tokens is not None and eval_duration_s > 0:
            tokens_per_sec = completion_tokens / eval_duration_s
    elif isinstance(total_duration_ns, (int, float)) and total_duration_ns > 0:
        eval_duration_ms = float(total_duration_ns) / NANOSECONDS_PER_MILLISECOND

    return {
        TOKEN_METRIC_PROMPT_TOKENS: prompt_tokens,
        TOKEN_METRIC_COMPLETION_TOKENS: completion_tokens,
        TOKEN_METRIC_TOTAL_TOKENS: total_tokens,
        TOKEN_METRIC_PROMPT_EVAL_DURATION_MS: prompt_eval_duration_ms,
        TOKEN_METRIC_EVAL_DURATION_MS: eval_duration_ms,
        TOKEN_METRIC_TTFT_MS: ttft_ms,
        TOKEN_METRIC_TOKENS_PER_SEC: tokens_per_sec,
    }


def parse_openai_token_metrics(payload: dict[str, object]) -> TokenMetrics:
    token_metrics = empty_token_metrics()
    raw_usage = payload.get(OPENAI_USAGE_FIELD)
    if not isinstance(raw_usage, dict):
        return token_metrics

    prompt_tokens = raw_usage.get(OPENAI_PROMPT_TOKENS_FIELD)
    completion_tokens = raw_usage.get(OPENAI_COMPLETION_TOKENS_FIELD)
    total_tokens = raw_usage.get(OPENAI_TOTAL_TOKENS_FIELD)
    if isinstance(prompt_tokens, int):
        token_metrics[TOKEN_METRIC_PROMPT_TOKENS] = max(0, prompt_tokens)
    if isinstance(completion_tokens, int):
        token_metrics[TOKEN_METRIC_COMPLETION_TOKENS] = max(0, completion_tokens)
    if isinstance(total_tokens, int):
        token_metrics[TOKEN_METRIC_TOTAL_TOKENS] = max(0, total_tokens)
    elif token_metrics[TOKEN_METRIC_PROMPT_TOKENS] is not None or token_metrics[TOKEN_METRIC_COMPLETION_TOKENS] is not None:
        token_metrics[TOKEN_METRIC_TOTAL_TOKENS] = int(token_metrics[TOKEN_METRIC_PROMPT_TOKENS] or 0) + int(
            token_metrics[TOKEN_METRIC_COMPLETION_TOKENS] or 0
        )
    return token_metrics


def record_provider_retry_event(
    logger: logging.Logger,
    identity: ProviderTelemetryIdentity,
    retry_telemetry: ProviderRetryTelemetry,
) -> None:
    logger.warning(
        "provider_retry provider=%s api=%s model=%s profile=%s operation=%s attempt=%s retry_budget=%s timeout_s=%s error_class=%s",
        identity.provider_name,
        identity.api_name,
        identity.model_name,
        identity.profile_name,
        retry_telemetry.operation,
        retry_telemetry.attempt + 1,
        retry_telemetry.max_retries,
        retry_telemetry.timeout_seconds,
        retry_telemetry.error.__class__.__name__,
    )
    _provider_facade().record_provider_retry(
        identity.provider_name,
        retry_telemetry.operation,
        identity.model_name,
    )


def record_provider_attempt_event(
    logger: logging.Logger,
    identity: ProviderTelemetryIdentity,
    attempt_telemetry: ProviderAttemptTelemetry,
) -> None:
    token_metrics = attempt_telemetry.token_metrics
    logger.info(
        "provider_request provider=%s api=%s model=%s profile=%s operation=%s attempt=%s retry_budget=%s timeout_s=%s outcome=%s error_class=%s duration_ms=%.2f ttft_ms=%s prompt_tokens=%s completion_tokens=%s total_tokens=%s tokens_per_sec=%s prompt_eval_duration_ms=%s eval_duration_ms=%s",
        identity.provider_name,
        identity.api_name,
        identity.model_name,
        identity.profile_name,
        attempt_telemetry.operation,
        attempt_telemetry.attempt + 1,
        attempt_telemetry.max_retries,
        attempt_telemetry.timeout_seconds,
        attempt_telemetry.outcome,
        "" if attempt_telemetry.last_error is None else attempt_telemetry.last_error.__class__.__name__,
        attempt_telemetry.duration_ms,
        _format_metric(token_metrics[TOKEN_METRIC_TTFT_MS], precision=2),
        _format_metric(token_metrics[TOKEN_METRIC_PROMPT_TOKENS]),
        _format_metric(token_metrics[TOKEN_METRIC_COMPLETION_TOKENS]),
        _format_metric(token_metrics[TOKEN_METRIC_TOTAL_TOKENS]),
        _format_metric(token_metrics[TOKEN_METRIC_TOKENS_PER_SEC], precision=4),
        _format_metric(token_metrics[TOKEN_METRIC_PROMPT_EVAL_DURATION_MS], precision=2),
        _format_metric(token_metrics[TOKEN_METRIC_EVAL_DURATION_MS], precision=2),
    )
    facade = _provider_facade()
    facade.record_provider_request(
        identity.provider_name,
        attempt_telemetry.operation,
        identity.model_name,
        attempt_telemetry.outcome,
        attempt_telemetry.duration_ms,
    )
    ttft_ms = token_metrics[TOKEN_METRIC_TTFT_MS]
    if ttft_ms is not None:
        facade.record_provider_ttft(
            identity.provider_name,
            attempt_telemetry.operation,
            identity.model_name,
            attempt_telemetry.outcome,
            ttft_ms,
        )
    tokens_per_sec = token_metrics[TOKEN_METRIC_TOKENS_PER_SEC]
    if tokens_per_sec is not None:
        facade.record_provider_tokens_per_sec(
            identity.provider_name,
            attempt_telemetry.operation,
            identity.model_name,
            attempt_telemetry.outcome,
            tokens_per_sec,
        )
    prompt_tokens = token_metrics[TOKEN_METRIC_PROMPT_TOKENS]
    completion_tokens = token_metrics[TOKEN_METRIC_COMPLETION_TOKENS]
    if prompt_tokens is not None and completion_tokens is not None:
        facade.record_provider_token_counts(
            identity.provider_name,
            attempt_telemetry.operation,
            identity.model_name,
            attempt_telemetry.outcome,
            prompt_tokens,
            completion_tokens,
        )


def record_inprocess_provider_request(
    provider_name: str,
    operation: str,
    model_name: str,
    outcome: str,
    duration_ms: float,
) -> None:
    _provider_facade().record_provider_request(provider_name, operation, model_name, outcome, duration_ms)


def record_provider_timeout_event(provider_name: str, operation: str, model_name: str) -> None:
    _provider_facade().record_provider_timeout(provider_name, operation, model_name)


def _format_metric(metric_value: float | int | None, *, precision: int | None = None) -> str:
    if metric_value is None:
        return ""
    if precision is None:
        return str(metric_value)
    return f"{metric_value:.{precision}f}"


def _provider_facade() -> ModuleType:
    from pipeline import llm_provider

    return llm_provider

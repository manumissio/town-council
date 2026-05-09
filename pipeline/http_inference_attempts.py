from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

import requests

from pipeline.http_inference_errors import response_error_for_client_http_error
from pipeline.inference_provider_contract import ProviderError
from pipeline.provider_telemetry import (
    ProviderAttemptTelemetry,
    ProviderRetryTelemetry,
    TokenMetrics,
    empty_token_metrics,
)


OUTCOME_OK: Final = "ok"
OUTCOME_ERROR: Final = "error"
OUTCOME_RESPONSE_ERROR: Final = "response_error"
OUTCOME_TIMEOUT: Final = "timeout"
OUTCOME_UNAVAILABLE: Final = "unavailable"
HTTP_PROVIDER_ATTEMPT_FAILURES: Final = (
    MemoryError,
    RuntimeError,
    OSError,
    OverflowError,
    TypeError,
    ValueError,
    AttributeError,
    KeyError,
)


@dataclass(frozen=True)
class HttpOperationContext:
    operation: str
    payload: dict[str, object]
    max_retries: int
    timeout_seconds: int
    post_generate_request: Callable[[dict[str, object], int], requests.Response]
    parse_response_payload: Callable[[requests.Response], tuple[str, TokenMetrics]]
    record_attempt_metrics: Callable[[ProviderAttemptTelemetry], None]
    record_retry: Callable[[ProviderRetryTelemetry], None]
    record_timeout: Callable[[str], None]


@dataclass(frozen=True)
class ProviderAttemptResult:
    text: str | None
    last_error: Exception | None
    stop_attempts: bool


def run_operation(context: HttpOperationContext) -> tuple[str | None, Exception | None]:
    last_error: Exception | None = None
    for attempt in range(context.max_retries + 1):
        attempt_result = run_attempt(context, attempt=attempt)
        if attempt_result.text is not None:
            return attempt_result.text, None
        last_error = attempt_result.last_error
        if attempt_result.stop_attempts:
            break
    return None, last_error


def run_attempt(context: HttpOperationContext, *, attempt: int) -> ProviderAttemptResult:
    t0 = time.perf_counter()
    outcome = OUTCOME_OK
    token_metrics = empty_token_metrics()
    last_error: Exception | None = None
    text = None
    stop_attempts = False
    try:
        response = context.post_generate_request(context.payload, context.timeout_seconds)
        response.raise_for_status()
        text, token_metrics = context.parse_response_payload(response)
    except requests.exceptions.HTTPError as error:
        outcome, last_error, stop_attempts = _handle_http_error(context, error, attempt=attempt)
    except requests.exceptions.Timeout as error:
        outcome, last_error = _handle_timeout(context, error, attempt=attempt)
    except requests.exceptions.RequestException as error:
        outcome, last_error = _handle_request_exception(context, error, attempt=attempt)
    except ProviderError as error:
        outcome = OUTCOME_RESPONSE_ERROR
        last_error = error
        stop_attempts = True
    except HTTP_PROVIDER_ATTEMPT_FAILURES as error:
        outcome = OUTCOME_ERROR
        last_error = error
    finally:
        duration_ms = (time.perf_counter() - t0) * 1000.0
        context.record_attempt_metrics(
            ProviderAttemptTelemetry(
                operation=context.operation,
                attempt=attempt,
                max_retries=context.max_retries,
                timeout_seconds=context.timeout_seconds,
                outcome=outcome,
                last_error=last_error,
                duration_ms=duration_ms,
                token_metrics=token_metrics,
            )
        )
    return ProviderAttemptResult(text=text, last_error=last_error, stop_attempts=stop_attempts)


def _handle_http_error(
    context: HttpOperationContext,
    error: requests.exceptions.HTTPError,
    *,
    attempt: int,
) -> tuple[str, Exception, bool]:
    response_error = response_error_for_client_http_error(error)
    if response_error is not None:
        return OUTCOME_RESPONSE_ERROR, response_error, True
    if attempt < context.max_retries:
        context.record_retry(
            ProviderRetryTelemetry(context.operation, attempt, context.max_retries, context.timeout_seconds, error)
        )
    return OUTCOME_UNAVAILABLE, error, False


def _handle_timeout(
    context: HttpOperationContext,
    error: requests.exceptions.Timeout,
    *,
    attempt: int,
) -> tuple[str, Exception]:
    context.record_timeout(context.operation)
    if attempt < context.max_retries:
        context.record_retry(
            ProviderRetryTelemetry(context.operation, attempt, context.max_retries, context.timeout_seconds, error)
        )
    return OUTCOME_TIMEOUT, error


def _handle_request_exception(
    context: HttpOperationContext,
    error: requests.exceptions.RequestException,
    *,
    attempt: int,
) -> tuple[str, Exception]:
    if attempt < context.max_retries:
        context.record_retry(
            ProviderRetryTelemetry(context.operation, attempt, context.max_retries, context.timeout_seconds, error)
        )
    return OUTCOME_UNAVAILABLE, error

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from types import ModuleType
from typing import Final

import requests

from pipeline.inference_provider_contract import (
    OPERATION_EXTRACT_AGENDA,
    OPERATION_GENERATE_JSON,
    OPERATION_GENERATE_TOPICS,
    OPERATION_SEGMENT_AGENDA,
    OPERATION_SUMMARIZE_AGENDA_ITEMS,
    OPERATION_SUMMARIZE_TEXT,
    RESPONSE_FIELD_NAME,
    ProviderError,
    ProviderResponseError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from pipeline.provider_telemetry import (
    ProviderAttemptTelemetry,
    ProviderRetryTelemetry,
    ProviderTelemetryIdentity,
    TokenMetrics,
    empty_token_metrics,
    parse_token_metrics,
    record_provider_attempt_event,
    record_provider_retry_event,
    record_provider_timeout_event,
)


logger = logging.getLogger("local-ai")

HTTP_PROVIDER_NAME: Final = "http"
MINIMUM_HTTP_TIMEOUT_SECONDS: Final = 5
HEALTH_CHECK_TIMEOUT_SECONDS: Final = 5
HTTP_CLIENT_ERROR_MIN_STATUS: Final = 400
HTTP_CLIENT_ERROR_MAX_STATUS: Final = 499
OUTCOME_OK: Final = "ok"
OUTCOME_ERROR: Final = "error"
OUTCOME_RESPONSE_ERROR: Final = "response_error"
OUTCOME_TIMEOUT: Final = "timeout"
OUTCOME_UNAVAILABLE: Final = "unavailable"
CONSERVATIVE_HTTP_PROFILE: Final = "conservative"
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


class HttpInferenceProvider:
    name = HTTP_PROVIDER_NAME

    def __init__(self):
        facade = _provider_facade()
        self.base_url = facade.LOCAL_AI_HTTP_BASE_URL
        self.timeout_seconds = max(MINIMUM_HTTP_TIMEOUT_SECONDS, facade.LOCAL_AI_HTTP_TIMEOUT_SECONDS)
        self.timeout_segment_seconds = max(MINIMUM_HTTP_TIMEOUT_SECONDS, facade.LOCAL_AI_HTTP_TIMEOUT_SEGMENT_SECONDS)
        self.timeout_summary_seconds = max(MINIMUM_HTTP_TIMEOUT_SECONDS, facade.LOCAL_AI_HTTP_TIMEOUT_SUMMARY_SECONDS)
        self.timeout_topics_seconds = max(MINIMUM_HTTP_TIMEOUT_SECONDS, facade.LOCAL_AI_HTTP_TIMEOUT_TOPICS_SECONDS)
        self.max_retries = max(0, facade.LOCAL_AI_HTTP_MAX_RETRIES)
        self.model_name = facade.LOCAL_AI_HTTP_MODEL

    def health_check(self) -> bool:
        try:
            response = _provider_facade().requests.get(
                f"{self.base_url}/api/tags",
                timeout=min(HEALTH_CHECK_TIMEOUT_SECONDS, self.timeout_seconds),
            )
            return bool(response.ok)
        except requests.exceptions.RequestException:
            return False

    def _timeout_for_operation(self, operation: str) -> int:
        # Workload classes pick timeout budgets; infra profiles own concurrency.
        if operation in {OPERATION_EXTRACT_AGENDA, OPERATION_SEGMENT_AGENDA, OPERATION_GENERATE_JSON}:
            return self.timeout_segment_seconds
        if operation in {OPERATION_SUMMARIZE_AGENDA_ITEMS, OPERATION_SUMMARIZE_TEXT}:
            return self.timeout_summary_seconds
        if operation == OPERATION_GENERATE_TOPICS:
            return self.timeout_topics_seconds
        return self.timeout_seconds

    def _max_retries_for_operation(self, operation: str) -> int:
        if operation == OPERATION_EXTRACT_AGENDA:
            return 0
        if self.max_retries <= 0:
            return 0
        if _provider_facade().LOCAL_AI_HTTP_PROFILE == CONSERVATIVE_HTTP_PROFILE and operation in {
            OPERATION_SUMMARIZE_AGENDA_ITEMS,
            OPERATION_SUMMARIZE_TEXT,
            OPERATION_GENERATE_TOPICS,
        }:
            return 0
        return self.max_retries

    def _build_request_payload(self, prompt: str, *, max_tokens: int, temperature: float) -> dict[str, object]:
        return {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_predict": int(max_tokens),
                "temperature": float(temperature),
            },
        }

    def _post_generate_request(self, payload: dict[str, object], *, timeout_seconds: int) -> requests.Response:
        return _provider_facade().requests.post(
            f"{self.base_url}/api/generate",
            json=payload,
            timeout=timeout_seconds,
        )

    def _parse_token_metrics(self, payload: dict[str, object]) -> TokenMetrics:
        return parse_token_metrics(payload)

    def _parse_response_payload(self, response: requests.Response) -> tuple[str, TokenMetrics]:
        try:
            payload = response.json()
        except ValueError as error:
            raise ProviderResponseError(f"Invalid JSON response payload: {error}") from error
        if not isinstance(payload, dict):
            raise ProviderResponseError("Invalid response payload type")

        token_metrics = self._parse_token_metrics(payload)
        raw_response = payload.get(RESPONSE_FIELD_NAME)
        if raw_response is None:
            raise ProviderResponseError("Missing response field in payload")
        if not isinstance(raw_response, str):
            raise ProviderResponseError("Invalid response field type in payload")
        text = raw_response.strip()
        if not text:
            raise ProviderResponseError("Empty response payload")
        return text, token_metrics

    def _record_retry(self, retry_telemetry: ProviderRetryTelemetry) -> None:
        record_provider_retry_event(logger, self._telemetry_identity(), retry_telemetry)

    def _record_attempt_metrics(self, attempt_telemetry: ProviderAttemptTelemetry) -> None:
        record_provider_attempt_event(logger, self._telemetry_identity(), attempt_telemetry)

    def _telemetry_identity(self) -> ProviderTelemetryIdentity:
        return ProviderTelemetryIdentity(
            provider_name=self.name,
            model_name=self.model_name,
            profile_name=_provider_facade().LOCAL_AI_HTTP_PROFILE,
        )

    def _run_operation(
        self,
        operation: str,
        prompt: str,
        *,
        max_tokens: int,
        temperature: float,
    ) -> str | None:
        payload = self._build_request_payload(prompt, max_tokens=max_tokens, temperature=temperature)
        last_error: Exception | None = None
        max_retries = self._max_retries_for_operation(operation)
        timeout_seconds = self._timeout_for_operation(operation)
        logger.info(
            "provider_policy provider=%s model=%s profile=%s operation=%s timeout_s=%s retry_budget=%s",
            self.name,
            self.model_name,
            _provider_facade().LOCAL_AI_HTTP_PROFILE,
            operation,
            timeout_seconds,
            max_retries,
        )
        for attempt in range(max_retries + 1):
            attempt_result = self._run_attempt(
                operation,
                payload,
                attempt=attempt,
                max_retries=max_retries,
                timeout_seconds=timeout_seconds,
            )
            if attempt_result.text is not None:
                return attempt_result.text
            last_error = attempt_result.last_error
            if attempt_result.stop_attempts:
                break

        _raise_provider_error_from_last_error(last_error)

    def _run_attempt(
        self,
        operation: str,
        payload: dict[str, object],
        *,
        attempt: int,
        max_retries: int,
        timeout_seconds: int,
    ) -> "_ProviderAttemptResult":
        t0 = time.perf_counter()
        outcome = OUTCOME_OK
        token_metrics = empty_token_metrics()
        last_error: Exception | None = None
        text = None
        stop_attempts = False
        try:
            response = self._post_generate_request(payload, timeout_seconds=timeout_seconds)
            response.raise_for_status()
            text, token_metrics = self._parse_response_payload(response)
        except requests.exceptions.HTTPError as error:
            outcome, last_error, stop_attempts = self._handle_http_error(
                operation,
                error,
                attempt=attempt,
                max_retries=max_retries,
                timeout_seconds=timeout_seconds,
            )
        except requests.exceptions.Timeout as error:
            outcome, last_error = self._handle_timeout(
                operation,
                error,
                attempt=attempt,
                max_retries=max_retries,
                timeout_seconds=timeout_seconds,
            )
        except requests.exceptions.RequestException as error:
            outcome, last_error = self._handle_request_exception(
                operation,
                error,
                attempt=attempt,
                max_retries=max_retries,
                timeout_seconds=timeout_seconds,
            )
        except ProviderError as error:
            outcome = OUTCOME_RESPONSE_ERROR
            last_error = error
            stop_attempts = True
        except HTTP_PROVIDER_ATTEMPT_FAILURES as error:
            outcome = OUTCOME_ERROR
            last_error = error
        finally:
            duration_ms = (time.perf_counter() - t0) * 1000.0
            self._record_attempt_metrics(
                ProviderAttemptTelemetry(
                    operation=operation,
                    attempt=attempt,
                    max_retries=max_retries,
                    timeout_seconds=timeout_seconds,
                    outcome=outcome,
                    last_error=last_error,
                    duration_ms=duration_ms,
                    token_metrics=token_metrics,
                )
            )
        return _ProviderAttemptResult(text=text, last_error=last_error, stop_attempts=stop_attempts)

    def _handle_http_error(
        self,
        operation: str,
        error: requests.exceptions.HTTPError,
        *,
        attempt: int,
        max_retries: int,
        timeout_seconds: int,
    ) -> tuple[str, Exception, bool]:
        status_code = getattr(getattr(error, "response", None), "status_code", None)
        if isinstance(status_code, int) and HTTP_CLIENT_ERROR_MIN_STATUS <= status_code <= HTTP_CLIENT_ERROR_MAX_STATUS:
            return OUTCOME_RESPONSE_ERROR, ProviderResponseError(f"HTTP inference client error: status={status_code}"), True
        if attempt < max_retries:
            self._record_retry(
                ProviderRetryTelemetry(operation, attempt, max_retries, timeout_seconds, error)
            )
        return OUTCOME_UNAVAILABLE, error, False

    def _handle_timeout(
        self,
        operation: str,
        error: requests.exceptions.Timeout,
        *,
        attempt: int,
        max_retries: int,
        timeout_seconds: int,
    ) -> tuple[str, Exception]:
        record_provider_timeout_event(self.name, operation, self.model_name)
        if attempt < max_retries:
            self._record_retry(ProviderRetryTelemetry(operation, attempt, max_retries, timeout_seconds, error))
        return OUTCOME_TIMEOUT, error

    def _handle_request_exception(
        self,
        operation: str,
        error: requests.exceptions.RequestException,
        *,
        attempt: int,
        max_retries: int,
        timeout_seconds: int,
    ) -> tuple[str, Exception]:
        if attempt < max_retries:
            self._record_retry(ProviderRetryTelemetry(operation, attempt, max_retries, timeout_seconds, error))
        return OUTCOME_UNAVAILABLE, error

    def extract_agenda(self, prompt: str, *, temperature: float, max_tokens: int) -> str | None:
        return self._run_operation(
            OPERATION_EXTRACT_AGENDA,
            prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    def summarize_agenda_items(self, prompt: str, *, temperature: float, max_tokens: int) -> str | None:
        return self._run_operation(
            OPERATION_SUMMARIZE_AGENDA_ITEMS,
            prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    def summarize_text(self, prompt: str, *, temperature: float, max_tokens: int) -> str | None:
        return self._run_operation(
            OPERATION_SUMMARIZE_TEXT,
            prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    def generate_topics(self, prompt: str, *, temperature: float, max_tokens: int) -> str | None:
        return self._run_operation(
            OPERATION_GENERATE_TOPICS,
            prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    def generate_json(self, prompt: str, *, max_tokens: int) -> str | None:
        return self._run_operation(OPERATION_GENERATE_JSON, prompt, max_tokens=max_tokens, temperature=0.0)


@dataclass(frozen=True)
class _ProviderAttemptResult:
    text: str | None
    last_error: Exception | None
    stop_attempts: bool


def _raise_provider_error_from_last_error(last_error: Exception | None) -> None:
    if isinstance(last_error, ProviderResponseError):
        raise last_error
    if isinstance(last_error, ProviderUnavailableError):
        raise last_error
    if isinstance(last_error, requests.exceptions.Timeout):
        raise ProviderTimeoutError(f"HTTP inference timed out: {last_error}") from last_error
    if last_error is not None:
        raise ProviderUnavailableError(f"HTTP inference unavailable: {last_error}") from last_error
    raise ProviderUnavailableError("HTTP inference unavailable")


def _provider_facade() -> ModuleType:
    from pipeline import llm_provider

    return llm_provider

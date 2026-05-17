from __future__ import annotations

import logging
from types import ModuleType

import requests

from pipeline.http_inference_attempts import HttpOperationContext, ProviderAttemptResult, run_attempt, run_operation
from pipeline.http_inference_errors import raise_provider_error_from_last_error
from pipeline.http_inference_payloads import (
    build_openai_compatible_request_payload,
    build_request_payload,
    parse_openai_compatible_response_payload,
    parse_response_payload,
)
from pipeline.http_inference_policy import (
    HEALTH_CHECK_TIMEOUT_SECONDS,
    HTTP_PROVIDER_NAME,
    MINIMUM_HTTP_TIMEOUT_SECONDS,
    max_retries_for_operation,
    timeout_for_operation,
)
from pipeline.http_inference_telemetry import log_provider_policy, record_attempt, record_retry, record_timeout
from pipeline.inference_provider_contract import (
    OPERATION_EXTRACT_AGENDA,
    OPERATION_GENERATE_JSON,
    OPERATION_GENERATE_TOPICS,
    OPERATION_SUMMARIZE_AGENDA_ITEMS,
    OPERATION_SUMMARIZE_TEXT,
)
from pipeline.provider_telemetry import (
    ProviderAttemptTelemetry,
    ProviderRetryTelemetry,
    ProviderTelemetryIdentity,
    TokenMetrics,
    parse_token_metrics,
)


logger = logging.getLogger("local-ai")
OPENAI_COMPAT_HTTP_API = "openai_compat"


class HttpInferenceProvider:
    name = HTTP_PROVIDER_NAME

    def __init__(self):
        facade = _provider_facade()
        self.base_url = facade.LOCAL_AI_HTTP_BASE_URL
        self.http_api = facade.LOCAL_AI_HTTP_API
        self.timeout_seconds = max(MINIMUM_HTTP_TIMEOUT_SECONDS, facade.LOCAL_AI_HTTP_TIMEOUT_SECONDS)
        self.timeout_segment_seconds = max(MINIMUM_HTTP_TIMEOUT_SECONDS, facade.LOCAL_AI_HTTP_TIMEOUT_SEGMENT_SECONDS)
        self.timeout_summary_seconds = max(MINIMUM_HTTP_TIMEOUT_SECONDS, facade.LOCAL_AI_HTTP_TIMEOUT_SUMMARY_SECONDS)
        self.timeout_topics_seconds = max(MINIMUM_HTTP_TIMEOUT_SECONDS, facade.LOCAL_AI_HTTP_TIMEOUT_TOPICS_SECONDS)
        self.max_retries = max(0, facade.LOCAL_AI_HTTP_MAX_RETRIES)
        self.model_name = facade.LOCAL_AI_HTTP_MODEL
        self.context_window = max(0, facade.LLM_CONTEXT_WINDOW)

    def health_check(self) -> bool:
        health_path = "/health" if self.http_api == OPENAI_COMPAT_HTTP_API else "/api/tags"
        try:
            response = _provider_facade().requests.get(
                f"{self.base_url}{health_path}",
                timeout=min(HEALTH_CHECK_TIMEOUT_SECONDS, self.timeout_seconds),
            )
            return bool(response.ok)
        except requests.exceptions.RequestException:
            return False

    def _timeout_for_operation(self, operation: str) -> int:
        return timeout_for_operation(
            operation,
            default_timeout_seconds=self.timeout_seconds,
            segment_timeout_seconds=self.timeout_segment_seconds,
            summary_timeout_seconds=self.timeout_summary_seconds,
            topics_timeout_seconds=self.timeout_topics_seconds,
        )

    def _max_retries_for_operation(self, operation: str) -> int:
        return max_retries_for_operation(
            operation,
            max_retries=self.max_retries,
            profile_name=_provider_facade().LOCAL_AI_HTTP_PROFILE,
        )

    def _build_request_payload(self, prompt: str, *, max_tokens: int, temperature: float) -> dict[str, object]:
        if self.http_api == OPENAI_COMPAT_HTTP_API:
            return build_openai_compatible_request_payload(
                prompt,
                model_name=self.model_name,
                max_tokens=max_tokens,
                temperature=temperature,
            )
        return build_request_payload(
            prompt,
            model_name=self.model_name,
            max_tokens=max_tokens,
            temperature=temperature,
            context_window=self.context_window,
        )

    def _post_generate_request(self, payload: dict[str, object], *, timeout_seconds: int) -> requests.Response:
        endpoint_path = "/v1/chat/completions" if self.http_api == OPENAI_COMPAT_HTTP_API else "/api/generate"
        return _provider_facade().requests.post(
            f"{self.base_url}{endpoint_path}",
            json=payload,
            timeout=timeout_seconds,
        )

    def _parse_token_metrics(self, payload: dict[str, object]) -> TokenMetrics:
        return parse_token_metrics(payload)

    def _parse_response_payload(self, response: requests.Response) -> tuple[str, TokenMetrics]:
        if self.http_api == OPENAI_COMPAT_HTTP_API:
            return parse_openai_compatible_response_payload(response)
        return parse_response_payload(response, token_metrics_parser=self._parse_token_metrics)

    def _record_retry(self, retry_telemetry: ProviderRetryTelemetry) -> None:
        record_retry(logger, self._telemetry_identity(), retry_telemetry)

    def _record_attempt_metrics(self, attempt_telemetry: ProviderAttemptTelemetry) -> None:
        record_attempt(logger, self._telemetry_identity(), attempt_telemetry)

    def _record_timeout(self, operation: str) -> None:
        record_timeout(self.name, operation, self.model_name)

    def _telemetry_identity(self) -> ProviderTelemetryIdentity:
        return ProviderTelemetryIdentity(
            provider_name=self.name,
            model_name=self.model_name,
            profile_name=_provider_facade().LOCAL_AI_HTTP_PROFILE,
            api_name=self.http_api,
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
        max_retries = self._max_retries_for_operation(operation)
        timeout_seconds = self._timeout_for_operation(operation)
        log_provider_policy(
            logger,
            self._telemetry_identity(),
            operation=operation,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        )
        text, last_error = run_operation(
            HttpOperationContext(
                operation,
                payload,
                max_retries=max_retries,
                timeout_seconds=timeout_seconds,
                post_generate_request=lambda request_payload, request_timeout: self._post_generate_request(
                    request_payload,
                    timeout_seconds=request_timeout,
                ),
                parse_response_payload=self._parse_response_payload,
                record_attempt_metrics=self._record_attempt_metrics,
                record_retry=self._record_retry,
                record_timeout=self._record_timeout,
            )
        )
        if text is not None:
            return text

        raise_provider_error_from_last_error(last_error)

    def _run_attempt(
        self,
        operation: str,
        payload: dict[str, object],
        *,
        attempt: int,
        max_retries: int,
        timeout_seconds: int,
    ) -> ProviderAttemptResult:
        return run_attempt(
            HttpOperationContext(
                operation,
                payload,
                max_retries=max_retries,
                timeout_seconds=timeout_seconds,
                post_generate_request=lambda request_payload, request_timeout: self._post_generate_request(
                    request_payload,
                    timeout_seconds=request_timeout,
                ),
                parse_response_payload=self._parse_response_payload,
                record_attempt_metrics=self._record_attempt_metrics,
                record_retry=self._record_retry,
                record_timeout=self._record_timeout,
            ),
            attempt=attempt,
        )

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


def _provider_facade() -> ModuleType:
    from pipeline import llm_provider

    return llm_provider

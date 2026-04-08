from __future__ import annotations

import logging
import time
from typing import Final, Protocol, runtime_checkable

import requests

from pipeline.config import (
    LOCAL_AI_HTTP_BASE_URL,
    LOCAL_AI_HTTP_PROFILE,
    LOCAL_AI_HTTP_TIMEOUT_SECONDS,
    LOCAL_AI_HTTP_TIMEOUT_SEGMENT_SECONDS,
    LOCAL_AI_HTTP_TIMEOUT_SUMMARY_SECONDS,
    LOCAL_AI_HTTP_TIMEOUT_TOPICS_SECONDS,
    LOCAL_AI_HTTP_MAX_RETRIES,
    LOCAL_AI_HTTP_MODEL,
)
from pipeline.metrics import (
    record_provider_token_counts,
    record_provider_tokens_per_sec,
    record_provider_request,
    record_provider_retry,
    record_provider_ttft,
    record_provider_timeout,
)


logger = logging.getLogger("local-ai")

OPERATION_EXTRACT_AGENDA: Final = "extract_agenda"
OPERATION_GENERATE_JSON: Final = "generate_json"
OPERATION_GENERATE_TOPICS: Final = "generate_topics"
OPERATION_SUMMARIZE_AGENDA_ITEMS: Final = "summarize_agenda_items"
OPERATION_SUMMARIZE_TEXT: Final = "summarize_text"

RESPONSE_FIELD_NAME: Final = "response"
PROMPT_EVAL_COUNT_FIELD: Final = "prompt_eval_count"
EVAL_COUNT_FIELD: Final = "eval_count"
PROMPT_EVAL_DURATION_FIELD: Final = "prompt_eval_duration"
EVAL_DURATION_FIELD: Final = "eval_duration"
TOTAL_DURATION_FIELD: Final = "total_duration"


class ProviderError(RuntimeError):
    """Base provider error type for orchestrator retry/fallback decisions."""


class ProviderTimeoutError(ProviderError):
    """Provider timed out waiting for inference response."""


class ProviderUnavailableError(ProviderError):
    """Provider endpoint unavailable or transport failed."""


class ProviderResponseError(ProviderError):
    """Provider returned malformed/invalid response payload."""


@runtime_checkable
class InferenceProvider(Protocol):
    def health_check(self) -> bool: ...

    def extract_agenda(self, prompt: str, *, temperature: float, max_tokens: int) -> str | None: ...

    def summarize_agenda_items(self, prompt: str, *, temperature: float, max_tokens: int) -> str | None: ...

    def summarize_text(self, prompt: str, *, temperature: float, max_tokens: int) -> str | None: ...

    def generate_topics(self, prompt: str, *, temperature: float, max_tokens: int) -> str | None: ...

    def generate_json(self, prompt: str, *, max_tokens: int) -> str | None: ...


class InProcessLlamaProvider:
    name = "inprocess"

    def __init__(self, owner):
        self.owner = owner
        self.model_name = "inprocess-llama"

    def health_check(self) -> bool:
        return True

    def _run_operation(
        self,
        operation: str,
        prompt: str,
        *,
        max_tokens: int,
        temperature: float,
        response_format: dict | None = None,
    ) -> str | None:
        self.owner._load_model()
        if not self.owner.llm:
            return None
        t0 = time.perf_counter()
        outcome = "ok"
        with self.owner._lock:
            try:
                if response_format is not None:
                    try:
                        response = self.owner.llm(
                            prompt,
                            max_tokens=max_tokens,
                            temperature=temperature,
                            response_format=response_format,
                        )
                    except TypeError:
                        response = self.owner.llm(
                            prompt,
                            max_tokens=max_tokens,
                            temperature=temperature,
                        )
                else:
                    response = self.owner.llm(
                        prompt,
                        max_tokens=max_tokens,
                        temperature=temperature,
                    )
                return ((response or {}).get("choices") or [{}])[0].get("text", "")
            except Exception as exc:
                outcome = "error"
                raise ProviderResponseError(str(exc)) from exc
            finally:
                duration_ms = (time.perf_counter() - t0) * 1000.0
                record_provider_request(self.name, operation, self.model_name, outcome, duration_ms)
                if self.owner.llm:
                    self.owner.llm.reset()

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
        return self._run_operation(
            OPERATION_GENERATE_JSON,
            prompt,
            max_tokens=max_tokens,
            temperature=0.0,
            response_format={"type": "json_object"},
        )


class HttpInferenceProvider:
    name = "http"

    def __init__(self):
        self.base_url = LOCAL_AI_HTTP_BASE_URL
        self.timeout_seconds = max(5, LOCAL_AI_HTTP_TIMEOUT_SECONDS)
        self.timeout_segment_seconds = max(5, LOCAL_AI_HTTP_TIMEOUT_SEGMENT_SECONDS)
        self.timeout_summary_seconds = max(5, LOCAL_AI_HTTP_TIMEOUT_SUMMARY_SECONDS)
        self.timeout_topics_seconds = max(5, LOCAL_AI_HTTP_TIMEOUT_TOPICS_SECONDS)
        self.max_retries = max(0, LOCAL_AI_HTTP_MAX_RETRIES)
        self.model_name = LOCAL_AI_HTTP_MODEL

    def health_check(self) -> bool:
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=min(5, self.timeout_seconds))
            return bool(response.ok)
        except Exception:
            return False

    def _timeout_for_operation(self, operation: str) -> int:
        # Keep transport policy hardware-agnostic: workload classes pick timeout budgets,
        # while actual concurrency control stays in infra profiles (OLLAMA_NUM_PARALLEL).
        if operation in {OPERATION_EXTRACT_AGENDA, "segment_agenda", OPERATION_GENERATE_JSON}:
            return self.timeout_segment_seconds
        if operation in {OPERATION_SUMMARIZE_AGENDA_ITEMS, OPERATION_SUMMARIZE_TEXT}:
            return self.timeout_summary_seconds
        if operation == OPERATION_GENERATE_TOPICS:
            return self.timeout_topics_seconds
        return self.timeout_seconds

    def _max_retries_for_operation(self, operation: str) -> int:
        # Agenda segmentation already has an in-process heuristic fallback. When the
        # HTTP path is saturated, repeating the same long extract_agenda call mostly
        # adds queue wait and retry churn before we use that fallback anyway.
        if operation == OPERATION_EXTRACT_AGENDA:
            return 0
        # Conservative mode should surface summary/topic timeouts back to Celery
        # promptly so we do not pay the same queue wait twice inside the provider.
        if self.max_retries <= 0:
            return 0
        if LOCAL_AI_HTTP_PROFILE == "conservative" and operation in {
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
        return requests.post(f"{self.base_url}/api/generate", json=payload, timeout=timeout_seconds)

    def _parse_token_metrics(self, payload: dict[str, object]) -> dict[str, float | int | None]:
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
            prompt_eval_duration_ms = float(prompt_eval_duration_ns) / 1_000_000.0
            ttft_ms = prompt_eval_duration_ms
        if isinstance(eval_duration_ns, (int, float)) and eval_duration_ns > 0:
            eval_duration_ms = float(eval_duration_ns) / 1_000_000.0
            eval_duration_s = float(eval_duration_ns) / 1_000_000_000.0
            if completion_tokens is not None and eval_duration_s > 0:
                tokens_per_sec = completion_tokens / eval_duration_s
        elif isinstance(total_duration_ns, (int, float)) and total_duration_ns > 0:
            eval_duration_ms = float(total_duration_ns) / 1_000_000.0

        return {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "prompt_eval_duration_ms": prompt_eval_duration_ms,
            "eval_duration_ms": eval_duration_ms,
            "ttft_ms": ttft_ms,
            "tokens_per_sec": tokens_per_sec,
        }

    def _parse_response_payload(self, response: requests.Response) -> tuple[str, dict[str, float | int | None]]:
        try:
            payload = response.json()
        except ValueError as exc:
            raise ProviderResponseError(f"Invalid JSON response payload: {exc}") from exc
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

    def _record_retry(self, operation: str, *, attempt: int, max_retries: int, timeout_seconds: int, error: Exception) -> None:
        logger.warning(
            "provider_retry provider=%s model=%s profile=%s operation=%s attempt=%s retry_budget=%s timeout_s=%s error_class=%s",
            self.name,
            self.model_name,
            LOCAL_AI_HTTP_PROFILE,
            operation,
            attempt + 1,
            max_retries,
            timeout_seconds,
            error.__class__.__name__,
        )
        record_provider_retry(self.name, operation, self.model_name)

    def _record_attempt_metrics(
        self,
        operation: str,
        *,
        attempt: int,
        max_retries: int,
        timeout_seconds: int,
        outcome: str,
        last_error: Exception | None,
        duration_ms: float,
        token_metrics: dict[str, float | int | None],
    ) -> None:
        logger.info(
            "provider_request provider=%s model=%s profile=%s operation=%s attempt=%s retry_budget=%s timeout_s=%s outcome=%s error_class=%s duration_ms=%.2f ttft_ms=%s prompt_tokens=%s completion_tokens=%s total_tokens=%s tokens_per_sec=%s prompt_eval_duration_ms=%s eval_duration_ms=%s",
            self.name,
            self.model_name,
            LOCAL_AI_HTTP_PROFILE,
            operation,
            attempt + 1,
            max_retries,
            timeout_seconds,
            outcome,
            "" if last_error is None else last_error.__class__.__name__,
            duration_ms,
            "" if token_metrics["ttft_ms"] is None else f"{token_metrics['ttft_ms']:.2f}",
            "" if token_metrics["prompt_tokens"] is None else str(token_metrics["prompt_tokens"]),
            "" if token_metrics["completion_tokens"] is None else str(token_metrics["completion_tokens"]),
            "" if token_metrics["total_tokens"] is None else str(token_metrics["total_tokens"]),
            "" if token_metrics["tokens_per_sec"] is None else f"{token_metrics['tokens_per_sec']:.4f}",
            "" if token_metrics["prompt_eval_duration_ms"] is None else f"{token_metrics['prompt_eval_duration_ms']:.2f}",
            "" if token_metrics["eval_duration_ms"] is None else f"{token_metrics['eval_duration_ms']:.2f}",
        )
        record_provider_request(self.name, operation, self.model_name, outcome, duration_ms)
        ttft_ms = token_metrics["ttft_ms"]
        if ttft_ms is not None:
            record_provider_ttft(self.name, operation, self.model_name, outcome, ttft_ms)
        tokens_per_sec = token_metrics["tokens_per_sec"]
        if tokens_per_sec is not None:
            record_provider_tokens_per_sec(self.name, operation, self.model_name, outcome, tokens_per_sec)
        prompt_tokens = token_metrics["prompt_tokens"]
        completion_tokens = token_metrics["completion_tokens"]
        if prompt_tokens is not None and completion_tokens is not None:
            record_provider_token_counts(
                self.name,
                operation,
                self.model_name,
                outcome,
                prompt_tokens,
                completion_tokens,
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
            LOCAL_AI_HTTP_PROFILE,
            operation,
            timeout_seconds,
            max_retries,
        )
        for attempt in range(max_retries + 1):
            t0 = time.perf_counter()
            outcome = "ok"
            token_metrics: dict[str, float | int | None] = {
                "prompt_tokens": None,
                "completion_tokens": None,
                "total_tokens": None,
                "prompt_eval_duration_ms": None,
                "eval_duration_ms": None,
                "ttft_ms": None,
                "tokens_per_sec": None,
            }
            try:
                response = self._post_generate_request(payload, timeout_seconds=timeout_seconds)
                response.raise_for_status()
                text, token_metrics = self._parse_response_payload(response)
                return text
            except requests.exceptions.HTTPError as exc:
                status_code = getattr(getattr(exc, "response", None), "status_code", None)
                if isinstance(status_code, int) and 400 <= status_code < 500:
                    outcome = "response_error"
                    last_error = ProviderResponseError(f"HTTP inference client error: status={status_code}")
                    break
                outcome = "unavailable"
                last_error = exc
                if attempt < max_retries:
                    self._record_retry(
                        operation,
                        attempt=attempt,
                        max_retries=max_retries,
                        timeout_seconds=timeout_seconds,
                        error=exc,
                    )
            except requests.exceptions.Timeout as exc:
                outcome = "timeout"
                last_error = exc
                record_provider_timeout(self.name, operation, self.model_name)
                if attempt < max_retries:
                    self._record_retry(
                        operation,
                        attempt=attempt,
                        max_retries=max_retries,
                        timeout_seconds=timeout_seconds,
                        error=exc,
                    )
            except requests.exceptions.RequestException as exc:
                outcome = "unavailable"
                last_error = exc
                if attempt < max_retries:
                    self._record_retry(
                        operation,
                        attempt=attempt,
                        max_retries=max_retries,
                        timeout_seconds=timeout_seconds,
                        error=exc,
                    )
            except ProviderError as exc:
                outcome = "response_error"
                last_error = exc
                break
            except Exception as exc:
                outcome = "error"
                last_error = exc
            finally:
                duration_ms = (time.perf_counter() - t0) * 1000.0
                self._record_attempt_metrics(
                    operation,
                    attempt=attempt,
                    max_retries=max_retries,
                    timeout_seconds=timeout_seconds,
                    outcome=outcome,
                    last_error=last_error,
                    duration_ms=duration_ms,
                    token_metrics=token_metrics,
                )

        if isinstance(last_error, ProviderResponseError):
            raise last_error
        if isinstance(last_error, ProviderUnavailableError):
            raise last_error
        if isinstance(last_error, requests.exceptions.Timeout):
            raise ProviderTimeoutError(f"HTTP inference timed out: {last_error}") from last_error
        if last_error is not None:
            raise ProviderUnavailableError(f"HTTP inference unavailable: {last_error}") from last_error
        raise ProviderUnavailableError("HTTP inference unavailable")

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

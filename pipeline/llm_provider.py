from __future__ import annotations

import logging
import time
from typing import Protocol, runtime_checkable

import requests

from pipeline.config import (
    LOCAL_AI_HTTP_BASE_URL,
    LOCAL_AI_HTTP_TIMEOUT_SECONDS,
    LOCAL_AI_HTTP_TIMEOUT_SEGMENT_SECONDS,
    LOCAL_AI_HTTP_TIMEOUT_SUMMARY_SECONDS,
    LOCAL_AI_HTTP_TIMEOUT_TOPICS_SECONDS,
    LOCAL_AI_HTTP_MAX_RETRIES,
    LOCAL_AI_HTTP_MODEL,
)
from pipeline.metrics import (
    record_provider_request,
    record_provider_retry,
    record_provider_timeout,
)


logger = logging.getLogger("local-ai")


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


class InProcessLlamaProvider:
    name = "inprocess"

    def __init__(self, owner):
        self.owner = owner
        self.model_name = "inprocess-llama"

    def health_check(self) -> bool:
        return True

    # Backward-compat shim for existing tests/callers during protocol migration.
    def generate(
        self,
        prompt: str,
        *,
        max_tokens: int,
        temperature: float,
        response_format: dict | None = None,
    ) -> str | None:
        return self._generate(
            "generate",
            prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            response_format=response_format,
        )

    def _generate(
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
        return self.generate(prompt, max_tokens=max_tokens, temperature=temperature)

    def summarize_agenda_items(self, prompt: str, *, temperature: float, max_tokens: int) -> str | None:
        return self.generate(prompt, max_tokens=max_tokens, temperature=temperature)

    def summarize_text(self, prompt: str, *, temperature: float, max_tokens: int) -> str | None:
        return self.generate(prompt, max_tokens=max_tokens, temperature=temperature)

    def generate_topics(self, prompt: str, *, temperature: float, max_tokens: int) -> str | None:
        return self.generate(prompt, max_tokens=max_tokens, temperature=temperature)

    def generate_json(self, prompt: str, *, max_tokens: int) -> str | None:
        return self._generate(
            "generate_json",
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
        self._operation_hint = "generate"

    def health_check(self) -> bool:
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=min(5, self.timeout_seconds))
            return bool(response.ok)
        except Exception:
            return False

    # Backward-compat shim for existing tests/callers during protocol migration.
    def generate(
        self,
        prompt: str,
        *,
        max_tokens: int,
        temperature: float,
        response_format: dict | None = None,
    ) -> str | None:
        _ = response_format
        operation = self._operation_hint or "generate"
        return self._generate(operation, prompt, max_tokens=max_tokens, temperature=temperature)

    def _call_with_operation(
        self,
        operation: str,
        prompt: str,
        *,
        max_tokens: int,
        temperature: float,
    ) -> str | None:
        prev = self._operation_hint
        self._operation_hint = operation
        try:
            # Use public generate() so test monkeypatches continue to work.
            return self.generate(prompt, max_tokens=max_tokens, temperature=temperature)
        finally:
            self._operation_hint = prev

    def _timeout_for_operation(self, operation: str) -> int:
        # Keep transport policy hardware-agnostic: workload classes pick timeout budgets,
        # while actual concurrency control stays in infra profiles (OLLAMA_NUM_PARALLEL).
        if operation in {"extract_agenda", "segment_agenda", "generate_json"}:
            return self.timeout_segment_seconds
        if operation in {"summarize_agenda_items", "summarize_text", "generate"}:
            return self.timeout_summary_seconds
        if operation in {"generate_topics"}:
            return self.timeout_topics_seconds
        return self.timeout_seconds

    def _generate(
        self,
        operation: str,
        prompt: str,
        *,
        max_tokens: int,
        temperature: float,
    ) -> str | None:
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_predict": int(max_tokens),
                "temperature": float(temperature),
            },
        }
        url = f"{self.base_url}/api/generate"
        last_error = None
        for attempt in range(self.max_retries + 1):
            timeout_seconds = self._timeout_for_operation(operation)
            t0 = time.perf_counter()
            outcome = "ok"
            try:
                response = requests.post(url, json=payload, timeout=timeout_seconds)
                response.raise_for_status()
                data = response.json()
                text = (data.get("response") or "").strip()
                if text is None:
                    outcome = "response_error"
                    raise ProviderResponseError("Empty response payload")
                return text
            except requests.exceptions.Timeout as exc:
                outcome = "timeout"
                last_error = exc
                record_provider_timeout(self.name, operation, self.model_name)
                if attempt < self.max_retries:
                    record_provider_retry(self.name, operation, self.model_name)
            except requests.exceptions.RequestException as exc:
                outcome = "unavailable"
                last_error = exc
                if attempt < self.max_retries:
                    record_provider_retry(self.name, operation, self.model_name)
            except ProviderError as exc:
                outcome = "response_error"
                last_error = exc
            except Exception as exc:
                outcome = "error"
                last_error = exc
            finally:
                duration_ms = (time.perf_counter() - t0) * 1000.0
                logger.info(
                    "provider_request provider=%s model=%s operation=%s attempt=%s outcome=%s duration_ms=%.2f",
                    self.name,
                    self.model_name,
                    operation,
                    attempt + 1,
                    outcome,
                    duration_ms,
                )
                record_provider_request(self.name, operation, self.model_name, outcome, duration_ms)

        if isinstance(last_error, ProviderResponseError):
            raise last_error
        if isinstance(last_error, requests.exceptions.Timeout):
            raise ProviderTimeoutError(f"HTTP inference timed out: {last_error}") from last_error
        if last_error is not None:
            raise ProviderUnavailableError(f"HTTP inference unavailable: {last_error}") from last_error
        raise ProviderUnavailableError("HTTP inference unavailable")

    def extract_agenda(self, prompt: str, *, temperature: float, max_tokens: int) -> str | None:
        return self._call_with_operation(
            "extract_agenda",
            prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    def summarize_agenda_items(self, prompt: str, *, temperature: float, max_tokens: int) -> str | None:
        return self._call_with_operation(
            "summarize_agenda_items",
            prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    def summarize_text(self, prompt: str, *, temperature: float, max_tokens: int) -> str | None:
        return self._call_with_operation(
            "summarize_text",
            prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    def generate_topics(self, prompt: str, *, temperature: float, max_tokens: int) -> str | None:
        return self._call_with_operation(
            "generate_topics",
            prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    def generate_json(self, prompt: str, *, max_tokens: int) -> str | None:
        return self._generate("generate_json", prompt, max_tokens=max_tokens, temperature=0.0)

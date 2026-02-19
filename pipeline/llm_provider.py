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
    record_provider_token_counts,
    record_provider_tokens_per_sec,
    record_provider_request,
    record_provider_retry,
    record_provider_ttft,
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
            prompt_tokens = None
            completion_tokens = None
            total_tokens = None
            prompt_eval_duration_ms = None
            eval_duration_ms = None
            ttft_ms = None
            tokens_per_sec = None
            try:
                response = requests.post(url, json=payload, timeout=timeout_seconds)
                response.raise_for_status()
                data = response.json()
                prompt_eval_count = data.get("prompt_eval_count")
                eval_count = data.get("eval_count")
                prompt_eval_duration_ns = data.get("prompt_eval_duration")
                eval_duration_ns = data.get("eval_duration")
                total_duration_ns = data.get("total_duration")

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
                    "provider_request provider=%s model=%s operation=%s attempt=%s outcome=%s duration_ms=%.2f ttft_ms=%s prompt_tokens=%s completion_tokens=%s total_tokens=%s tokens_per_sec=%s prompt_eval_duration_ms=%s eval_duration_ms=%s",
                    self.name,
                    self.model_name,
                    operation,
                    attempt + 1,
                    outcome,
                    duration_ms,
                    "" if ttft_ms is None else f"{ttft_ms:.2f}",
                    "" if prompt_tokens is None else str(prompt_tokens),
                    "" if completion_tokens is None else str(completion_tokens),
                    "" if total_tokens is None else str(total_tokens),
                    "" if tokens_per_sec is None else f"{tokens_per_sec:.4f}",
                    "" if prompt_eval_duration_ms is None else f"{prompt_eval_duration_ms:.2f}",
                    "" if eval_duration_ms is None else f"{eval_duration_ms:.2f}",
                )
                record_provider_request(self.name, operation, self.model_name, outcome, duration_ms)
                if ttft_ms is not None:
                    record_provider_ttft(self.name, operation, self.model_name, outcome, ttft_ms)
                if tokens_per_sec is not None:
                    record_provider_tokens_per_sec(self.name, operation, self.model_name, outcome, tokens_per_sec)
                if prompt_tokens is not None and completion_tokens is not None:
                    record_provider_token_counts(
                        self.name,
                        operation,
                        self.model_name,
                        outcome,
                        prompt_tokens,
                        completion_tokens,
                    )

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

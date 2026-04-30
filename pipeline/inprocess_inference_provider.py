from __future__ import annotations

import time
from typing import Final

from pipeline.inference_provider_contract import (
    OPERATION_EXTRACT_AGENDA,
    OPERATION_GENERATE_JSON,
    OPERATION_GENERATE_TOPICS,
    OPERATION_SUMMARIZE_AGENDA_ITEMS,
    OPERATION_SUMMARIZE_TEXT,
    ProviderResponseError,
)
from pipeline.provider_telemetry import record_inprocess_provider_request


INPROCESS_PROVIDER_FAILURES: Final = (AssertionError, RuntimeError, ValueError, TypeError, AttributeError, KeyError)
INPROCESS_PROVIDER_NAME: Final = "inprocess"
INPROCESS_MODEL_NAME: Final = "inprocess-llama"


class InProcessLlamaProvider:
    name = INPROCESS_PROVIDER_NAME

    def __init__(self, owner):
        self.owner = owner
        self.model_name = INPROCESS_MODEL_NAME

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
                response = self._call_model(
                    prompt,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    response_format=response_format,
                )
                return ((response or {}).get("choices") or [{}])[0].get("text", "")
            except INPROCESS_PROVIDER_FAILURES as error:
                outcome = "error"
                raise ProviderResponseError(str(error)) from error
            finally:
                duration_ms = (time.perf_counter() - t0) * 1000.0
                record_inprocess_provider_request(self.name, operation, self.model_name, outcome, duration_ms)
                if self.owner.llm:
                    self.owner.llm.reset()

    def _call_model(
        self,
        prompt: str,
        *,
        max_tokens: int,
        temperature: float,
        response_format: dict | None,
    ):
        if response_format is None:
            return self.owner.llm(
                prompt,
                max_tokens=max_tokens,
                temperature=temperature,
            )
        try:
            return self.owner.llm(
                prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                response_format=response_format,
            )
        except TypeError:
            return self.owner.llm(
                prompt,
                max_tokens=max_tokens,
                temperature=temperature,
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
        return self._run_operation(
            OPERATION_GENERATE_JSON,
            prompt,
            max_tokens=max_tokens,
            temperature=0.0,
            response_format={"type": "json_object"},
        )

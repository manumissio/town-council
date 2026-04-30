from __future__ import annotations

from typing import Final, Protocol, runtime_checkable


OPERATION_EXTRACT_AGENDA: Final = "extract_agenda"
OPERATION_GENERATE_JSON: Final = "generate_json"
OPERATION_GENERATE_TOPICS: Final = "generate_topics"
OPERATION_SEGMENT_AGENDA: Final = "segment_agenda"
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

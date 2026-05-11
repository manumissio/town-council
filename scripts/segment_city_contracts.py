from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from sqlalchemy.orm import Session

DEFAULT_CATALOG_TIMEOUT_SECONDS = 120
SEGMENT_COUNT_KEYS = (
    "complete",
    "empty",
    "failed",
    "timed_out",
    "other",
    "timeout_fallbacks",
    "empty_response_fallbacks",
    "llm_attempted",
    "llm_skipped_heuristic_first",
    "heuristic_complete",
    "llm_timeout_then_fallback",
)

SegmentPayload = dict[str, int | str | None]
ProgressCallback = Callable[[str, int, int, int, str, float], None]


class SessionScope(Protocol):
    def __enter__(self) -> Session: ...

    def __exit__(self, _exc_type: object, exc: object, _traceback: object) -> object: ...


class SessionFactory(Protocol):
    def __call__(self) -> SessionScope: ...


@dataclass(frozen=True)
class SegmentSelectionServices:
    db_session: SessionFactory
    source_aliases_for_city: Callable[[str], set[str]]


@dataclass(frozen=True)
class SegmentWorkerServices:
    db_session: SessionFactory
    segment_catalog_with_mode: Callable[..., dict[str, Any]]
    segment_timeout_override: Callable[[int | None], Any]
    capture_agenda_fallback_events: Callable[[], Any]
    mark_catalog_failed: Callable[[int, str], None] | None = None


def empty_segment_counts() -> dict[str, int]:
    return {key: 0 for key in SEGMENT_COUNT_KEYS}

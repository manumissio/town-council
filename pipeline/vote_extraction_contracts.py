from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol, TypedDict

from pipeline.models import AgendaItem


LLM_EXTRACTED_VOTE_SOURCE = "llm_extracted"
SKIP_REASON_MISSING_TITLE = "missing_title"
SKIP_REASON_TRUSTED_SOURCE = "trusted_source"
SKIP_REASON_ALREADY_HIGH_CONFIDENCE = "already_high_confidence"
SKIP_REASON_EXISTING_RESULT = "existing_result"
SKIP_REASON_INSUFFICIENT_TEXT = "insufficient_text"
SKIP_REASON_LOW_CONFIDENCE = "low_confidence"
SKIP_REASON_UNKNOWN_NO_TALLY = "unknown_no_tally"

VALID_OUTCOME_LABELS = {
    "passed",
    "failed",
    "deferred",
    "continued",
    "tabled",
    "withdrawn",
    "no_action",
    "unknown",
}

OUTCOME_SYNONYMS = {
    "approved": "passed",
    "adopted": "passed",
    "carried": "passed",
    "accepted": "passed",
    "rejected": "failed",
    "did_not_pass": "failed",
    "did not pass": "failed",
    "denied": "failed",
    "postponed": "continued",
    "held over": "continued",
    "continued to": "continued",
    "referred": "deferred",
    "reconsidered later": "deferred",
    "laid over": "tabled",
    "pulled": "withdrawn",
    "removed": "withdrawn",
    "received and filed": "no_action",
    "discussion only": "no_action",
    "none": "unknown",
    "n/a": "unknown",
}

UNKNOWN_RESULT_VALUES = {"", "unknown", "n/a", "na", "none", "pending", "tbd"}
TRUSTED_VOTE_SOURCES = {"legistar", "manual"}
VOTE_KEYWORDS = (
    "motion",
    "moved",
    "seconded",
    "ayes",
    "noes",
    "abstain",
    "absent",
    "vote",
    "carried",
    "passed",
    "failed",
    "unanimous",
)


class VoteExtractionModel(Protocol):
    def generate_json(self, prompt: str, max_tokens: int) -> str | None: ...


class AgendaItemLike(Protocol):
    id: object
    title: object
    description: object
    result: object
    votes: object


class AgendaItemQuery(Protocol):
    def filter_by(self, **kwargs: object) -> "AgendaItemQuery": ...
    def order_by(self, *args: object) -> "AgendaItemQuery": ...
    def all(self) -> list[AgendaItemLike]: ...


class AgendaItemSession(Protocol):
    def query(self, model: type[AgendaItem]) -> AgendaItemQuery: ...


class CatalogLike(Protocol):
    id: object
    content: str | None


class EventLike(Protocol):
    name: object
    record_date: object


class DocumentLike(Protocol):
    event: EventLike | None


class VoteExtractionCounters(TypedDict):
    processed_items: int
    updated_items: int
    skipped_items: int
    failed_items: int
    skip_reasons: dict[str, int]


@dataclass(slots=True)
class VoteExtractionResult:
    outcome_label: str
    confidence: float
    motion_text: str | None = None
    vote_tally_raw: str | None = None
    yes_count: int | None = None
    no_count: int | None = None
    abstain_count: int | None = None
    absent_count: int | None = None
    evidence_snippet: str | None = None


PromptBuilder = Callable[[str, str, str], str]
CatalogVoteExtractor = Callable[[VoteExtractionModel, str, str, str], VoteExtractionResult]
VoteContextBuilder = Callable[[str, str, str | None], str]
VoteResultTextBuilder = Callable[[str], str]
ExistingVoteChecker = Callable[[object], bool]
ExistingResultChecker = Callable[[object | None], bool]


@dataclass(frozen=True, slots=True)
class VoteExtractionSettings:
    confidence_threshold: float
    context_after_chars: int
    context_before_chars: int
    max_tokens: int
    min_text_chars: int


@dataclass(frozen=True, slots=True)
class VoteExtractionRuntimeHooks:
    vote_extractor: CatalogVoteExtractor | None = None
    context_builder: VoteContextBuilder | None = None
    trusted_vote_checker: ExistingVoteChecker | None = None
    high_confidence_vote_checker: ExistingVoteChecker | None = None
    existing_result_checker: ExistingResultChecker | None = None
    result_text_builder: VoteResultTextBuilder | None = None


DEFAULT_RUNTIME_HOOKS = VoteExtractionRuntimeHooks()

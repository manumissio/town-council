from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class SemanticConfigError(RuntimeError):
    """Raised for unsafe or unsupported semantic backend configuration."""


@dataclass
class SemanticCandidate:
    row_id: int
    score: float
    metadata: dict[str, Any]


@dataclass
class SemanticRerankResult:
    candidates: list[SemanticCandidate]
    diagnostics: dict[str, Any]


@dataclass
class BuildResult:
    row_count: int
    catalog_count: int
    source_counts: dict[str, int]
    corpus_hash: str
    model_name: str
    built_at: str


class SemanticBackend:
    def build_index(self, db) -> BuildResult:  # pragma: no cover - interface
        raise NotImplementedError

    def query(self, query_text: str, top_k: int) -> list[SemanticCandidate]:  # pragma: no cover - interface
        raise NotImplementedError

    def health(self) -> dict[str, Any]:  # pragma: no cover - interface
        raise NotImplementedError

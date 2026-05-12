from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Protocol


SEMANTIC_DIAGNOSTIC_DEFAULTS: dict[str, object] = {
    "retrieval_mode": "vector_direct",
    "result_scope": "full_semantic",
    "hybrid_rerank_applied": False,
    "degraded_to_lexical": False,
    "skipped_reason": None,
    "lexical_candidates": 0,
    "eligible_meeting_candidates": 0,
    "candidate_limit_applied": 0,
    "fresh_embeddings": 0,
    "missing_embeddings": 0,
    "stale_embeddings": 0,
    "lexical_fallback_candidates": 0,
}
LEXICAL_ATTRIBUTES_TO_RETRIEVE = [
    "id",
    "db_id",
    "event_id",
    "catalog_id",
    "result_type",
    "city",
    "meeting_category",
    "organization",
    "date",
]


class SemanticCandidateLike(Protocol):
    score: float
    metadata: dict[str, Any]


@dataclass(frozen=True)
class SemanticRetrievalSettings:
    backend_name: str
    base_top_k: int
    filter_expansion_factor: int
    max_top_k: int
    rerank_candidate_limit: int


@dataclass(frozen=True)
class SemanticSearchFilters:
    city: str | None
    meeting_type: str | None
    org: str | None
    date_from: str | None
    date_to: str | None
    include_agenda_items: bool


@dataclass
class SemanticRetrievalResult:
    deduped: list[SemanticCandidateLike]
    raw_count: int
    filtered_count: int
    k_used: int
    expansion_steps: int
    diagnostics_extra: dict[str, Any]


FilterMatcher = Callable[[dict[str, Any], dict[str, Any]], bool]
DedupeCandidates = Callable[[list[SemanticCandidateLike]], list[SemanticCandidateLike]]
MergeLexicalFallback = Callable[[list[SemanticCandidateLike], list[dict[str, Any]], dict[str, Any]], tuple[list[Any], int]]
BuildFilterClauses = Callable[..., list[str]]


def initial_top_k(target: int, settings: SemanticRetrievalSettings) -> int:
    return min(settings.max_top_k, max(settings.base_top_k, target * settings.filter_expansion_factor))


def lexical_candidate_limit(target: int, settings: SemanticRetrievalSettings) -> int:
    return min(settings.max_top_k, max(target * settings.filter_expansion_factor, settings.rerank_candidate_limit))


def build_lexical_search_params(
    search_filters: SemanticSearchFilters,
    *,
    target: int,
    settings: SemanticRetrievalSettings,
    build_filter_clauses: BuildFilterClauses,
) -> dict[str, Any]:
    lexical_params: dict[str, Any] = {
        "limit": lexical_candidate_limit(target, settings),
        "offset": 0,
        "attributesToRetrieve": LEXICAL_ATTRIBUTES_TO_RETRIEVE,
        "filter": build_filter_clauses(
            city=search_filters.city,
            meeting_type=search_filters.meeting_type,
            org=search_filters.org,
            date_from=search_filters.date_from,
            date_to=search_filters.date_to,
            include_agenda_items=search_filters.include_agenda_items,
        ),
    }
    if not lexical_params["filter"]:
        del lexical_params["filter"]
    return lexical_params


def retrieve_semantic_candidates(
    *,
    backend: Any,
    db: Any,
    query_text: str,
    target: int,
    filters: dict[str, Any],
    search_filters: SemanticSearchFilters,
    settings: SemanticRetrievalSettings,
    meili_client: Any,
    is_pgvector_backend: bool,
    build_filter_clauses: BuildFilterClauses,
    filter_matcher: FilterMatcher,
    dedupe_candidates: DedupeCandidates,
    merge_lexical_fallback: MergeLexicalFallback,
) -> SemanticRetrievalResult:
    k = initial_top_k(target, settings)
    if is_pgvector_backend or settings.backend_name == "pgvector":
        return _retrieve_pgvector_candidates(
            backend=backend,
            db=db,
            query_text=query_text,
            target=target,
            filters=filters,
            search_filters=search_filters,
            settings=settings,
            meili_client=meili_client,
            k=k,
            build_filter_clauses=build_filter_clauses,
            filter_matcher=filter_matcher,
            dedupe_candidates=dedupe_candidates,
            merge_lexical_fallback=merge_lexical_fallback,
        )
    return _retrieve_direct_vector_candidates(
        backend=backend,
        query_text=query_text,
        target=target,
        filters=filters,
        settings=settings,
        k=k,
        filter_matcher=filter_matcher,
        dedupe_candidates=dedupe_candidates,
    )


def _retrieve_pgvector_candidates(
    *,
    backend: Any,
    db: Any,
    query_text: str,
    target: int,
    filters: dict[str, Any],
    search_filters: SemanticSearchFilters,
    settings: SemanticRetrievalSettings,
    meili_client: Any,
    k: int,
    build_filter_clauses: BuildFilterClauses,
    filter_matcher: FilterMatcher,
    dedupe_candidates: DedupeCandidates,
    merge_lexical_fallback: MergeLexicalFallback,
) -> SemanticRetrievalResult:
    diagnostics_extra: dict[str, Any] = dict(SEMANTIC_DIAGNOSTIC_DEFAULTS)
    lexical_params = build_lexical_search_params(
        search_filters,
        target=target,
        settings=settings,
        build_filter_clauses=build_filter_clauses,
    )
    lexical_results = meili_client.index("documents").search(query_text, lexical_params)
    lexical_hits = lexical_results.get("hits", []) or []
    candidates = _rerank_pgvector_candidates(backend, db, query_text, lexical_hits, k, diagnostics_extra)
    filtered = [candidate for candidate in candidates if filter_matcher(candidate.metadata, filters)]
    deduped = dedupe_candidates(filtered)
    if diagnostics_extra.get("degraded_to_lexical") or len(deduped) < target:
        deduped, fallback_added = merge_lexical_fallback(deduped, lexical_hits, filters)
        diagnostics_extra["degraded_to_lexical"] = True
        diagnostics_extra["lexical_fallback_candidates"] = fallback_added
        if fallback_added and diagnostics_extra.get("skipped_reason") is None:
            diagnostics_extra["skipped_reason"] = "partial_embedding_coverage"
    return SemanticRetrievalResult(
        deduped=deduped,
        raw_count=len(lexical_hits),
        filtered_count=len(filtered),
        k_used=k,
        expansion_steps=0,
        diagnostics_extra=diagnostics_extra,
    )


def _rerank_pgvector_candidates(
    backend: Any,
    db: Any,
    query_text: str,
    lexical_hits: list[dict[str, Any]],
    k: int,
    diagnostics_extra: dict[str, Any],
) -> list[SemanticCandidateLike]:
    rerank_with_diagnostics = getattr(backend, "rerank_candidates_with_diagnostics", None)
    if callable(rerank_with_diagnostics):
        rerank_result = rerank_with_diagnostics(db, query_text, lexical_hits, top_k=k)
        diagnostics_extra.update(rerank_result.diagnostics)
        return rerank_result.candidates
    return backend.rerank_candidates(db, query_text, lexical_hits, top_k=k)


def _retrieve_direct_vector_candidates(
    *,
    backend: Any,
    query_text: str,
    target: int,
    filters: dict[str, Any],
    settings: SemanticRetrievalSettings,
    k: int,
    filter_matcher: FilterMatcher,
    dedupe_candidates: DedupeCandidates,
) -> SemanticRetrievalResult:
    diagnostics_extra: dict[str, Any] = dict(SEMANTIC_DIAGNOSTIC_DEFAULTS)
    expansion_steps = 0
    while True:
        candidates = backend.query(query_text, k)
        filtered = [candidate for candidate in candidates if filter_matcher(candidate.metadata, filters)]
        deduped = dedupe_candidates(filtered)
        if len(deduped) >= target or k >= settings.max_top_k:
            break
        next_k = min(settings.max_top_k, max(k + 1, k * 2))
        if next_k == k:
            break
        k = next_k
        expansion_steps += 1
    return SemanticRetrievalResult(
        deduped=deduped,
        raw_count=len(candidates),
        filtered_count=len(filtered),
        k_used=k,
        expansion_steps=expansion_steps,
        diagnostics_extra=diagnostics_extra,
    )

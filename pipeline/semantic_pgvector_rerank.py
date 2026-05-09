from __future__ import annotations

from typing import Any

from sqlalchemy import bindparam, text

from pipeline.models import Catalog
from pipeline.semantic_backend_types import SemanticCandidate, SemanticRerankResult
from pipeline.semantic_text import _safe_text, catalog_semantic_source_hash


def _semantic_index_facade():
    from pipeline import semantic_index

    return semantic_index


def _initial_diagnostics(lexical_hits: list[dict]) -> dict[str, Any]:
    return {
        "retrieval_mode": "hybrid_pgvector",
        "result_scope": "meeting_hybrid",
        "hybrid_rerank_applied": False,
        "degraded_to_lexical": False,
        "skipped_reason": None,
        "lexical_candidates": len(lexical_hits),
        "eligible_meeting_candidates": 0,
        "candidate_limit_applied": 0,
        "fresh_embeddings": 0,
        "missing_embeddings": 0,
        "stale_embeddings": 0,
        "lexical_fallback_candidates": 0,
    }


def _meeting_db_id(hit: dict) -> int | None:
    db_id = hit.get("db_id")
    if db_id is not None:
        return int(db_id)
    raw_id = str(hit.get("id") or "")
    if not raw_id.startswith("doc_"):
        return None
    try:
        return int(raw_id.split("_", 1)[1])
    except (IndexError, ValueError):
        return None


def _candidate_rows(lexical_hits: list[dict]) -> list[dict]:
    candidate_rows = []
    for hit in lexical_hits:
        if str(hit.get("result_type") or "") != "meeting":
            continue
        db_id = _meeting_db_id(hit)
        catalog_id = hit.get("catalog_id")
        if db_id is None or catalog_id is None:
            continue
        candidate_rows.append(
            {
                "db_id": db_id,
                "catalog_id": int(catalog_id),
                "meta": {
                    "result_type": "meeting",
                    "catalog_id": int(catalog_id),
                    "db_id": db_id,
                    "event_id": hit.get("event_id"),
                    "city": str(hit.get("city") or "").lower(),
                    "meeting_category": hit.get("meeting_category") or "Other",
                    "organization": hit.get("organization") or "City Council",
                    "date": hit.get("date"),
                    "source_type": "summary",
                },
            }
        )
    return candidate_rows


def _expected_hash_by_catalog(db, catalog_ids: list[int]) -> dict[int, str | None]:
    expected_hash_rows = db.query(Catalog.id, Catalog.summary).filter(Catalog.id.in_(catalog_ids)).all()
    return {int(catalog_id): catalog_semantic_source_hash(summary) for catalog_id, summary in expected_hash_rows}


def _scored_rows(db, query_literal: str, catalog_ids: list[int]):
    semantic_index = _semantic_index_facade()
    stmt = text(
        """
            SELECT
              se.catalog_id AS catalog_id,
              se.source_hash AS source_hash,
              (1 - (se.embedding <=> CAST(:query_vec AS vector))) AS score
            FROM semantic_embedding se
            WHERE se.catalog_id IN :catalog_ids
              AND se.model_name = :model_name
              AND se.embedding IS NOT NULL
            ORDER BY se.embedding <=> CAST(:query_vec AS vector)
            LIMIT :limit
            """
    ).bindparams(bindparam("catalog_ids", expanding=True))
    return list(
        db.execute(
            stmt,
            {
                "query_vec": query_literal,
                "catalog_ids": catalog_ids,
                "model_name": semantic_index.SEMANTIC_MODEL_NAME,
                "limit": max(1, len(catalog_ids)),
            },
        ).mappings()
    )


def _fresh_candidates(scored_rows, by_catalog, expected_hash_by_catalog, diagnostics) -> list[SemanticCandidate]:
    candidates: list[SemanticCandidate] = []
    seen_catalogs: set[int] = set()
    for row in scored_rows:
        catalog_id = int(row["catalog_id"])
        expected_hash = expected_hash_by_catalog.get(catalog_id)
        if expected_hash is None or row.get("source_hash") != expected_hash:
            diagnostics["stale_embeddings"] += 1
            continue
        base = by_catalog.get(catalog_id)
        if not base or catalog_id in seen_catalogs:
            continue
        seen_catalogs.add(catalog_id)
        candidates.append(
            SemanticCandidate(row_id=len(candidates), score=float(row.get("score") or 0.0), metadata=base["meta"])
        )
    return candidates


def _empty_result(diagnostics: dict[str, Any], reason: str, *, degraded: bool = False) -> SemanticRerankResult:
    diagnostics["skipped_reason"] = reason
    diagnostics["degraded_to_lexical"] = degraded
    return SemanticRerankResult(candidates=[], diagnostics=diagnostics)


def _rows_by_catalog(candidate_rows: list[dict]) -> dict[int, dict]:
    rows_by_catalog: dict[int, dict] = {}
    for row in candidate_rows:
        catalog_id = int(row["catalog_id"])
        if catalog_id not in rows_by_catalog:
            rows_by_catalog[catalog_id] = row
    return rows_by_catalog


def _fresh_embedding_gap_reason(diagnostics: dict[str, Any]) -> str:
    if diagnostics["missing_embeddings"] > 0 and diagnostics["stale_embeddings"] == 0:
        return "missing_embeddings"
    if diagnostics["stale_embeddings"] > 0 and diagnostics["missing_embeddings"] == 0:
        return "stale_embeddings"
    return "insufficient_fresh_embeddings"


def _successful_rerank_result(
    *,
    candidates: list[SemanticCandidate],
    diagnostics: dict[str, Any],
    top_k: int,
    catalog_count: int,
) -> SemanticRerankResult:
    diagnostics["hybrid_rerank_applied"] = True
    diagnostics["degraded_to_lexical"] = len(candidates) < min(max(1, int(top_k)), catalog_count)
    if diagnostics["degraded_to_lexical"] and diagnostics["skipped_reason"] is None:
        diagnostics["skipped_reason"] = "partial_embedding_coverage"
    return SemanticRerankResult(candidates=candidates[: max(1, int(top_k))], diagnostics=diagnostics)


def rerank_candidates_with_diagnostics(
    backend, db, query_text: str, lexical_hits: list[dict], top_k: int
) -> SemanticRerankResult:
    diagnostics = _initial_diagnostics(lexical_hits)
    if not lexical_hits:
        return _empty_result(diagnostics, "no_lexical_candidates")

    query = _safe_text(query_text)
    if not query:
        return _empty_result(diagnostics, "empty_query")

    candidate_rows = _candidate_rows(lexical_hits)
    diagnostics["eligible_meeting_candidates"] = len(candidate_rows)
    if not candidate_rows:
        return _empty_result(diagnostics, "no_meeting_candidates", degraded=True)

    by_catalog = _rows_by_catalog(candidate_rows)
    semantic_index = _semantic_index_facade()
    catalog_ids = list(by_catalog.keys())[: max(1, semantic_index.SEMANTIC_RERANK_CANDIDATE_LIMIT)]
    diagnostics["candidate_limit_applied"] = len(catalog_ids)
    if not catalog_ids:
        return _empty_result(diagnostics, "no_candidate_catalogs", degraded=True)

    query_literal = backend._vector_literal(backend._encode([query])[0])
    expected_hashes = _expected_hash_by_catalog(db, catalog_ids)
    scored = _scored_rows(db, query_literal, catalog_ids)
    candidates = _fresh_candidates(scored, by_catalog, expected_hashes, diagnostics)

    diagnostics["fresh_embeddings"] = len(candidates)
    diagnostics["missing_embeddings"] = max(0, len(catalog_ids) - len(scored))
    if not candidates:
        return _empty_result(diagnostics, _fresh_embedding_gap_reason(diagnostics), degraded=True)

    return _successful_rerank_result(
        candidates=candidates,
        diagnostics=diagnostics,
        top_k=top_k,
        catalog_count=len(catalog_ids),
    )

import logging
import os
import time
from typing import Any, Optional

import meilisearch
from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session as SQLAlchemySession, sessionmaker

from pipeline.config import (
    SEMANTIC_ENABLED,
    SEMANTIC_BACKEND,
    SEMANTIC_BASE_TOP_K,
    SEMANTIC_FILTER_EXPANSION_FACTOR,
    SEMANTIC_MAX_TOP_K,
    SEMANTIC_RERANK_CANDIDATE_LIMIT,
)
from pipeline.models import db_connect
from pipeline.semantic_index import (
    get_semantic_backend,
    SemanticConfigError,
    PgvectorSemanticBackend,
)
from semantic_service.candidates import (
    dedupe_semantic_candidates as _dedupe_semantic_candidates,
    lexical_hit_to_candidate as _lexical_hit_to_candidate,
    semantic_candidate_key as _semantic_candidate_key,
    semantic_candidate_matches_filters as _semantic_candidate_matches_filters,
)
from semantic_service.filters import (
    build_filter_values as _build_filter_values,
    build_meilisearch_filter_clauses as _build_meilisearch_filter_clauses,
    validate_date_format,
)
from semantic_service.hydration import (
    SemanticResponseTiming,
    build_semantic_search_response,
    hydrate_agenda_hits,
    hydrate_meeting_hits,
)
from semantic_service.retrieval import (
    SemanticRetrievalSettings,
    SemanticSearchFilters,
    retrieve_semantic_candidates,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("town-council-semantic")

MEILI_HOST = os.getenv("MEILI_HOST", "http://meilisearch:7700")
MEILI_MASTER_KEY = os.getenv("MEILI_MASTER_KEY", "masterKey")
client = meilisearch.Client(MEILI_HOST, MEILI_MASTER_KEY, timeout=5)

engine = db_connect()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

app = FastAPI(title="Town Council Semantic Service")

SEMANTIC_BACKEND_UNHEALTHY_DETAIL = "Semantic backend unhealthy"
SEMANTIC_SERVICE_MISCONFIGURED_DETAIL = "Semantic service is misconfigured"
SEMANTIC_BACKEND_HEALTH_OK_STATUS = "ok"
SEMANTIC_BACKEND_HEALTH_ENGINES = {"faiss", "numpy", "pgvector"}
SEMANTIC_HEALTH_DIAGNOSTIC_ERRORS = (
    FileNotFoundError,
    OSError,
    RuntimeError,
    SemanticConfigError,
    ValueError,
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _public_semantic_backend_engine(engine_name: str | None) -> str | None:
    if engine_name is None:
        return None
    normalized_engine = engine_name.lower()
    return normalized_engine if normalized_engine in SEMANTIC_BACKEND_HEALTH_ENGINES else None


def _public_semantic_backend_health(backend_health: dict[str, Any]) -> dict[str, Any]:
    # The backend payload may contain exception details; build a fresh public shape instead of echoing it.
    return {
        "status": SEMANTIC_BACKEND_HEALTH_OK_STATUS,
        "engine": _public_semantic_backend_engine(backend_health.get("engine")),
    }


def _semantic_backend_engine_for_diagnostics(backend: Any) -> str | None:
    try:
        backend_health = backend.health()
    except SEMANTIC_HEALTH_DIAGNOSTIC_ERRORS as exc:
        logger.warning("semantic backend health diagnostic failed: %s", exc)
        return None
    if backend_health.get("status") != "ok":
        logger.warning("semantic backend health diagnostic returned unhealthy status: %s", backend_health)
        return None
    return _public_semantic_backend_engine(backend_health.get("engine"))


def _merge_semantic_with_lexical_fallback(semantic_candidates, lexical_hits: list[dict], filters: dict):
    merged = list(semantic_candidates)
    seen_keys = {_semantic_candidate_key(candidate) for candidate in semantic_candidates}
    added = 0
    for order_idx, hit in enumerate(lexical_hits):
        candidate = _lexical_hit_to_candidate(hit, order_idx)
        if candidate is None:
            continue
        if not _semantic_candidate_matches_filters(candidate.metadata, filters):
            continue
        key = _semantic_candidate_key(candidate)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        merged.append(candidate)
        added += 1
    return merged, added


def _hydrate_meeting_hits(db: SQLAlchemySession, candidates: list) -> list[dict]:
    return hydrate_meeting_hits(db, candidates)


def _hydrate_agenda_hits(db: SQLAlchemySession, candidates: list) -> list[dict]:
    return hydrate_agenda_hits(db, candidates)


@app.get("/health")
def health_check(db: SQLAlchemySession = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        if not SEMANTIC_ENABLED:
            return {"status": "healthy", "database": "connected", "semantic_enabled": False}
        backend_health = get_semantic_backend().health()
        if backend_health.get("status") != "ok":
            logger.warning("semantic backend health returned unhealthy status: %s", backend_health)
            raise HTTPException(status_code=503, detail=SEMANTIC_BACKEND_UNHEALTHY_DETAIL)
        return {
            "status": "healthy",
            "database": "connected",
            "semantic_enabled": True,
            "backend": _public_semantic_backend_health(backend_health),
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("semantic health failed: %s", exc)
        raise HTTPException(status_code=503, detail="Semantic service unhealthy") from exc


@app.get("/search/semantic")
def search_documents_semantic(
    q: str = Query(..., min_length=1),
    city: Optional[str] = Query(None),
    include_agenda_items: bool = Query(False),
    meeting_type: Optional[str] = Query(None),
    org: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: SQLAlchemySession = Depends(get_db),
):
    if not SEMANTIC_ENABLED:
        raise HTTPException(
            status_code=503,
            detail="Semantic search is disabled. Set SEMANTIC_ENABLED=true and build artifacts.",
        )
    if date_from:
        validate_date_format(date_from)
    if date_to:
        validate_date_format(date_to)

    filters = _build_filter_values(
        city=city,
        meeting_type=meeting_type,
        org=org,
        date_from=date_from,
        date_to=date_to,
        include_agenda_items=include_agenda_items,
    )
    target = offset + limit
    t0 = time.perf_counter()
    backend = get_semantic_backend()

    try:
        retrieval_result = retrieve_semantic_candidates(
            backend=backend,
            db=db,
            query_text=q,
            target=target,
            filters=filters,
            search_filters=SemanticSearchFilters(
                city=city,
                meeting_type=meeting_type,
                org=org,
                date_from=date_from,
                date_to=date_to,
                include_agenda_items=include_agenda_items,
            ),
            settings=SemanticRetrievalSettings(
                backend_name=SEMANTIC_BACKEND,
                base_top_k=SEMANTIC_BASE_TOP_K,
                filter_expansion_factor=SEMANTIC_FILTER_EXPANSION_FACTOR,
                max_top_k=SEMANTIC_MAX_TOP_K,
                rerank_candidate_limit=SEMANTIC_RERANK_CANDIDATE_LIMIT,
            ),
            meili_client=client,
            is_pgvector_backend=isinstance(backend, PgvectorSemanticBackend),
            build_filter_clauses=_build_meilisearch_filter_clauses,
            filter_matcher=_semantic_candidate_matches_filters,
            dedupe_candidates=_dedupe_semantic_candidates,
            merge_lexical_fallback=_merge_semantic_with_lexical_fallback,
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "Semantic index artifacts are missing. "
                "Run `docker compose run --rm semantic python ../pipeline/reindex_semantic.py` and retry."
            ),
        ) from exc
    except SemanticConfigError as exc:
        logger.error("semantic search configuration failed: %s", exc)
        raise HTTPException(status_code=503, detail=SEMANTIC_SERVICE_MISCONFIGURED_DETAIL) from exc
    except Exception as exc:
        logger.error("semantic search failed: %s", exc)
        raise HTTPException(status_code=500, detail="Internal semantic search error") from exc

    engine = _semantic_backend_engine_for_diagnostics(backend)
    return build_semantic_search_response(
        db=db,
        retrieval_result=retrieval_result,
        limit=limit,
        offset=offset,
        timing=SemanticResponseTiming(started_at=t0, engine=engine),
        hydrate_meetings=_hydrate_meeting_hits,
        hydrate_agenda_items=_hydrate_agenda_hits,
    )

import logging
import os
import time
from typing import Optional, Any

import meilisearch
from fastapi import FastAPI, HTTPException, Query, Depends
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
from pipeline.models import db_connect, Document, Event, Place, Catalog, AgendaItem, Organization
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
    doc_ids = [int(c.metadata.get("db_id") or 0) for c in candidates if int(c.metadata.get("db_id") or 0) > 0]
    if not doc_ids:
        return []
    rows = (
        db.query(Document, Catalog, Event, Place, Organization)
        .join(Catalog, Document.catalog_id == Catalog.id)
        .join(Event, Document.event_id == Event.id)
        .join(Place, Document.place_id == Place.id)
        .outerjoin(Organization, Event.organization_id == Organization.id)
        .filter(Document.id.in_(doc_ids))
        .all()
    )
    by_doc_id = {}
    for doc, catalog, event, place, organization in rows:
        by_doc_id[doc.id] = {
            "id": f"doc_{doc.id}",
            "db_id": doc.id,
            "ocd_id": event.ocd_id,
            "result_type": "meeting",
            "catalog_id": catalog.id,
            "filename": catalog.filename,
            "url": catalog.url,
            "content": (catalog.content or "")[:5000] if catalog.content else None,
            "summary": catalog.summary,
            "summary_extractive": catalog.summary_extractive,
            "topics": catalog.topics,
            "related_ids": catalog.related_ids,
            "summary_is_stale": bool(
                catalog.summary and (not catalog.content_hash or catalog.summary_source_hash != catalog.content_hash)
            ),
            "topics_is_stale": bool(
                catalog.topics is not None and (not catalog.content_hash or catalog.topics_source_hash != catalog.content_hash)
            ),
            "people_metadata": [],
            "event_name": event.name,
            "meeting_category": event.meeting_type or "Other",
            "organization": organization.name if organization else "City Council",
            "date": event.record_date.isoformat() if event.record_date else None,
            "city": place.display_name or place.name,
            "state": place.state,
        }

    hydrated = []
    for cand in candidates:
        doc_id = int(cand.metadata.get("db_id") or 0)
        hit = by_doc_id.get(doc_id)
        if not hit:
            continue
        enriched = dict(hit)
        enriched["semantic_score"] = round(float(cand.score), 6)
        hydrated.append(enriched)
    return hydrated


def _hydrate_agenda_hits(db: SQLAlchemySession, candidates: list) -> list[dict]:
    item_ids = [int(c.metadata.get("db_id") or 0) for c in candidates if int(c.metadata.get("db_id") or 0) > 0]
    if not item_ids:
        return []
    rows = (
        db.query(AgendaItem, Event, Place, Organization)
        .join(Event, AgendaItem.event_id == Event.id)
        .join(Place, Event.place_id == Place.id)
        .outerjoin(Organization, Event.organization_id == Organization.id)
        .filter(AgendaItem.id.in_(item_ids))
        .all()
    )
    by_item_id = {}
    for item, event, place, org in rows:
        by_item_id[item.id] = {
            "id": f"item_{item.id}",
            "db_id": item.id,
            "ocd_id": item.ocd_id,
            "result_type": "agenda_item",
            "title": item.title,
            "description": item.description,
            "classification": item.classification,
            "result": item.result,
            "page_number": item.page_number,
            "event_name": event.name,
            "date": event.record_date.isoformat() if event.record_date else None,
            "city": place.display_name or place.name,
            "organization": org.name if org else "City Council",
            "meeting_category": event.meeting_type or "Other",
            "catalog_id": item.catalog_id,
            "url": item.catalog.url if item.catalog else None,
        }
    hydrated = []
    for cand in candidates:
        item_id = int(cand.metadata.get("db_id") or 0)
        hit = by_item_id.get(item_id)
        if not hit:
            continue
        enriched = dict(hit)
        enriched["semantic_score"] = round(float(cand.score), 6)
        hydrated.append(enriched)
    return hydrated


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
    k = max(SEMANTIC_BASE_TOP_K, target * SEMANTIC_FILTER_EXPANSION_FACTOR)
    k = min(k, SEMANTIC_MAX_TOP_K)
    expansion_steps = 0
    t0 = time.perf_counter()
    backend = get_semantic_backend()

    try:
        deduped = []
        raw_count = 0
        filtered_count = 0
        diagnostics_extra = {
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

        if isinstance(backend, PgvectorSemanticBackend) or (SEMANTIC_BACKEND == "pgvector"):
            index = client.index("documents")
            lexical_limit = min(
                SEMANTIC_MAX_TOP_K,
                max(target * SEMANTIC_FILTER_EXPANSION_FACTOR, SEMANTIC_RERANK_CANDIDATE_LIMIT),
            )
            lexical_params = {
                "limit": lexical_limit,
                "offset": 0,
                "attributesToRetrieve": [
                    "id",
                    "db_id",
                    "event_id",
                    "catalog_id",
                    "result_type",
                    "city",
                    "meeting_category",
                    "organization",
                    "date",
                ],
                "filter": _build_meilisearch_filter_clauses(
                    city=city,
                    meeting_type=meeting_type,
                    org=org,
                    date_from=date_from,
                    date_to=date_to,
                    include_agenda_items=include_agenda_items,
                ),
            }
            if not lexical_params["filter"]:
                del lexical_params["filter"]
            lexical_results = index.search(q, lexical_params)
            lexical_hits = lexical_results.get("hits", []) or []
            raw_count = len(lexical_hits)
            rerank_with_diagnostics = getattr(backend, "rerank_candidates_with_diagnostics", None)
            if callable(rerank_with_diagnostics):
                rerank_result = rerank_with_diagnostics(db, q, lexical_hits, top_k=k)
                candidates = rerank_result.candidates
                diagnostics_extra.update(rerank_result.diagnostics)
            else:
                candidates = backend.rerank_candidates(db, q, lexical_hits, top_k=k)
            filtered = [c for c in candidates if _semantic_candidate_matches_filters(c.metadata, filters)]
            filtered_count = len(filtered)
            deduped = _dedupe_semantic_candidates(filtered)
            if diagnostics_extra.get("degraded_to_lexical") or len(deduped) < target:
                deduped, fallback_added = _merge_semantic_with_lexical_fallback(deduped, lexical_hits, filters)
                diagnostics_extra["degraded_to_lexical"] = True
                diagnostics_extra["lexical_fallback_candidates"] = fallback_added
                if fallback_added and diagnostics_extra.get("skipped_reason") is None:
                    diagnostics_extra["skipped_reason"] = "partial_embedding_coverage"
        else:
            while True:
                candidates = backend.query(q, k)
                raw_count = len(candidates)
                filtered = [c for c in candidates if _semantic_candidate_matches_filters(c.metadata, filters)]
                filtered_count = len(filtered)
                deduped = _dedupe_semantic_candidates(filtered)
                if len(deduped) >= target or k >= SEMANTIC_MAX_TOP_K:
                    break
                next_k = min(SEMANTIC_MAX_TOP_K, max(k + 1, k * 2))
                if next_k == k:
                    break
                k = next_k
                expansion_steps += 1
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

    page_candidates = deduped[offset : offset + limit]
    meeting_candidates = [c for c in page_candidates if str(c.metadata.get("result_type") or "meeting") == "meeting"]
    agenda_candidates = [c for c in page_candidates if str(c.metadata.get("result_type")) == "agenda_item"]
    meeting_hits = _hydrate_meeting_hits(db, meeting_candidates)
    agenda_hits = _hydrate_agenda_hits(db, agenda_candidates)
    meeting_by_db = {hit["db_id"]: hit for hit in meeting_hits}
    agenda_by_db = {hit["db_id"]: hit for hit in agenda_hits}
    hits = []
    for cand in page_candidates:
        result_type = str(cand.metadata.get("result_type") or "meeting")
        db_id = int(cand.metadata.get("db_id") or 0)
        hit = meeting_by_db.get(db_id) if result_type == "meeting" else agenda_by_db.get(db_id)
        if hit:
            hits.append(hit)
    elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
    engine = _semantic_backend_engine_for_diagnostics(backend)
    return {
        "hits": hits,
        "estimatedTotalHits": len(deduped),
        "limit": limit,
        "offset": offset,
        "semantic_diagnostics": {
            "raw_candidates": raw_count,
            "filtered_candidates": filtered_count,
            "dedup_candidates": len(deduped),
            "k_used": k,
            "expansion_steps": expansion_steps,
            "latency_ms": elapsed_ms,
            "engine": engine,
            **diagnostics_extra,
        },
    }

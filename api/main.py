import sys
import os
import logging
import hmac
import re
import time
import csv
import io
from datetime import date, datetime, timedelta
import meilisearch
from meilisearch.errors import MeilisearchCommunicationError, MeilisearchTimeoutError, MeilisearchError
from fastapi import FastAPI, HTTPException, Query, Path, Depends, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse, Response
from typing import List, Optional
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as SQLAlchemySession, sessionmaker, joinedload
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text
from api.cache import cached
from pipeline.config import (
    SEMANTIC_ENABLED,
    SEMANTIC_BACKEND,
    SEMANTIC_BASE_TOP_K,
    SEMANTIC_FILTER_EXPANSION_FACTOR,
    SEMANTIC_MAX_TOP_K,
    SEMANTIC_RERANK_CANDIDATE_LIMIT,
    FEATURE_TRENDS_DASHBOARD,
)
from pipeline.semantic_index import get_semantic_backend, SemanticConfigError, PgvectorSemanticBackend

# Metrics are internal-only and are scraped by Prometheus from the Docker network.
from api.metrics import instrument_app

# Set up Rate Limiting
# This prevents a single user from overwhelming our local CPU with AI requests.
limiter = Limiter(key_func=get_remote_address)

# Set up structured logging for production observability
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("town-council-api")

# Add the project root to the python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# We initialize these as None first. If the import works, we fill them.
SessionLocal = None
agenda_items_look_low_quality = None

try:
    from pipeline.models import db_connect, Document, Event, Place, Catalog, Person, AgendaItem, DataIssue, IssueType, Membership, Organization
    from pipeline.content_hash import compute_content_hash
    from pipeline.summary_quality import analyze_source_text, is_source_summarizable, is_source_topicable, build_low_signal_message
    from pipeline.startup_purge import run_startup_purge_if_enabled
    from pipeline.utils import generate_ocd_id
    from pipeline.llm import LocalAI
    from pipeline.agenda_resolver import agenda_items_look_low_quality
    engine = db_connect()
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
except Exception as e:
    logger.error(f"CRITICAL: Could not load database models: {e}")

def is_db_ready():
    return SessionLocal is not None

# Security & Reliability: Dependency Injection for database sessions.
def get_db():
    if not is_db_ready():
        raise HTTPException(status_code=503, detail="Database service is unavailable")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# SECURITY: API Key Verification
# This ensures that only authorized users (like our frontend) can 
# trigger expensive AI tasks or report issues.
async def verify_api_key(request: Request, x_api_key: str = Header(None)):
    expected_key = os.getenv("API_AUTH_KEY", "dev_secret_key_change_me")
    # Constant-time comparison reduces timing side-channels.
    if not hmac.compare_digest(x_api_key or "", expected_key):
        client_ip = request.client.host if request and request.client else "unknown"
        logger.warning(
            "Unauthorized API access attempt: invalid or missing API key",
            extra={"client_ip": client_ip, "path": request.url.path},
        )
        raise HTTPException(status_code=401, detail="Invalid or missing API Key")

# PERFORMANCE: Use ORJSONResponse for 3-5x faster JSON serialization
app = FastAPI(
    title="Town Council Search API", 
    description="Search and retrieve local government meeting minutes.",
    default_response_class=ORJSONResponse
)

# Add /metrics and request timing counters (route-template labels to avoid cardinality blowups).
instrument_app(app)

# SECURITY: Startup Guardrail
# Warn the administrator if they forgot to change the default secret.
@app.on_event("startup")
async def check_security_config():
    key = os.getenv("API_AUTH_KEY", "dev_secret_key_change_me")
    if key == "dev_secret_key_change_me":
        logger.critical("SECURITY WARNING: You are using the default API Key. Please set API_AUTH_KEY in production.")
    # Startup purge is lock-protected. If another service already purged, we skip.
    purge_result = run_startup_purge_if_enabled()
    logger.info(f"startup_purge_result={purge_result}")
    if SEMANTIC_ENABLED:
        try:
            # Semantic backend is process-local and memory-heavy; validate startup safety early.
            health = get_semantic_backend().health()
            logger.info(f"semantic_backend_health={health}")
        except SemanticConfigError as exc:
            logger.critical(f"Semantic backend misconfiguration: {exc}")
            raise


# Add Rate Limit handler to the app
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# SECURITY: Global Error Interceptor
# This catches any crash (500 error) and hides the stack trace from the user.
# The user gets "Internal Server Error", but we get the full details in the secure server logs.
@app.middleware("http")
async def catch_exceptions_middleware(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception as e:
        logger.error(f"Unhandled Exception: {str(e)}", exc_info=True)
        return ORJSONResponse(
            status_code=500,
            content={"detail": "Internal Server Error. Our team has been notified."}
        )

# Initialize Local AI (Singleton)
# This wrapper function allows us to 'inject' the AI model into endpoints.
def get_local_ai():
    return LocalAI()

# SECURITY: Restrict CORS (Cross-Origin Resource Sharing)
# We load the allowed domains from the environment.
allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-API-Key"],
)

# Meilisearch Config
MEILI_HOST = os.getenv('MEILI_HOST', 'http://meilisearch:7700')
MEILI_MASTER_KEY = os.getenv('MEILI_MASTER_KEY', 'masterKey')

# SECURITY: We add a timeout to prevent 'Hanging Requests' from 
# locking up our server if Meilisearch is slow or down.
client = meilisearch.Client(MEILI_HOST, MEILI_MASTER_KEY, timeout=5)

@app.get("/")
def read_root():
    return {"status": "ok", "message": "Town Council API is running. Go to /docs for the Swagger UI."}

# ... existing imports ...

# Add Date Validation Helper
def validate_date_format(date_str: str):
    """Ensures date is YYYY-MM-DD"""
    if not re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")


def sanitize_filter(val: str) -> str:
    """Escape quotes in user input before using it in query-style filters."""
    return str(val).replace('"', '\\"')


def normalize_city_filter(val: str) -> str:
    """
    Accept either human labels ("Cupertino") or indexed keys ("ca_cupertino").
    """
    raw = (val or "").strip()
    lowered = raw.lower()
    if re.search(r'[^a-z0-9_\-\s]', lowered):
        return lowered
    slug = re.sub(r"[\s\-]+", "_", lowered).strip("_")
    if re.match(r"^[a-z]{2}_.+", slug):
        return slug
    return f"ca_{slug}" if slug else lowered


def _build_filter_values(
    city: Optional[str],
    meeting_type: Optional[str],
    org: Optional[str],
    date_from: Optional[str],
    date_to: Optional[str],
    include_agenda_items: bool,
) -> dict:
    """
    Build normalized filter values once so keyword and semantic search stay consistent.
    """
    normalized_city = normalize_city_filter(city) if city else None
    return {
        "city": normalized_city,
        "meeting_type": meeting_type,
        "org": org,
        "date_from": date_from,
        "date_to": date_to,
        "include_agenda_items": include_agenda_items,
    }


def _build_meilisearch_filter_clauses(
    city: Optional[str],
    meeting_type: Optional[str],
    org: Optional[str],
    date_from: Optional[str],
    date_to: Optional[str],
    include_agenda_items: bool,
) -> list[str]:
    clauses: list[str] = []
    if not include_agenda_items:
        clauses.append('result_type = "meeting"')
    if city:
        clauses.append(f'city = "{sanitize_filter(normalize_city_filter(city))}"')
    if meeting_type:
        clauses.append(f'meeting_category = "{sanitize_filter(meeting_type)}"')
    if org:
        clauses.append(f'organization = "{sanitize_filter(org)}"')
    if date_from and date_to:
        clauses.append(
            f'date >= "{sanitize_filter(date_from)}" AND date <= "{sanitize_filter(date_to)}"'
        )
    elif date_from:
        clauses.append(f'date >= "{sanitize_filter(date_from)}"')
    elif date_to:
        clauses.append(f'date <= "{sanitize_filter(date_to)}"')
    return clauses


def _require_trends_feature() -> None:
    if not FEATURE_TRENDS_DASHBOARD:
        raise HTTPException(status_code=503, detail="Trends dashboard is disabled")


def _bucket_start(value: date, granularity: str) -> date:
    if granularity == "quarter":
        q_month = ((value.month - 1) // 3) * 3 + 1
        return date(value.year, q_month, 1)
    return date(value.year, value.month, 1)


def _next_bucket_start(value: date, granularity: str) -> date:
    if granularity == "quarter":
        month = value.month + 3
    else:
        month = value.month + 1
    year = value.year
    while month > 12:
        month -= 12
        year += 1
    return date(year, month, 1)


def _iter_time_buckets(start: date, end: date, granularity: str) -> list[tuple[date, date]]:
    cursor = _bucket_start(start, granularity)
    out: list[tuple[date, date]] = []
    while cursor <= end:
        nxt = _next_bucket_start(cursor, granularity)
        bucket_end = min(end, nxt - timedelta(days=1))
        out.append((cursor, bucket_end))
        cursor = nxt
    return out


def _facet_topics(city: Optional[str], date_from: Optional[str], date_to: Optional[str]) -> dict:
    index = client.index("documents")
    filters = _build_meilisearch_filter_clauses(
        city=city,
        meeting_type=None,
        org=None,
        date_from=date_from,
        date_to=date_to,
        include_agenda_items=False,
    )
    params = {
        "limit": 0,
        "facets": ["topics"],
    }
    if filters:
        params["filter"] = filters
    result = index.search("", params)
    return result.get("facetDistribution", {}).get("topics", {}) or {}


def _parse_iso_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").date()
    except Exception:
        return None


def _collect_meeting_docs(city: Optional[str], scan_limit: int = 2000) -> list[dict]:
    """
    Fetch meeting docs from Meilisearch for application-side trend aggregation.
    """
    index = client.index("documents")
    filters = _build_meilisearch_filter_clauses(
        city=city,
        meeting_type=None,
        org=None,
        date_from=None,
        date_to=None,
        include_agenda_items=False,
    )
    out: list[dict] = []
    offset = 0
    page_size = 200
    while offset < scan_limit:
        params = {
            "limit": min(page_size, scan_limit - offset),
            "offset": offset,
            "attributesToRetrieve": ["topics", "date", "city"],
            "filter": filters,
        }
        if not filters:
            del params["filter"]
        page = index.search("", params)
        hits = page.get("hits", []) or []
        out.extend(hits)
        if len(hits) < page_size:
            break
        offset += len(hits)
    return out


def _count_topics_from_docs(
    docs: list[dict],
    date_from: Optional[str],
    date_to: Optional[str],
) -> dict[str, int]:
    start = _parse_iso_date(date_from)
    end = _parse_iso_date(date_to)
    counts: dict[str, int] = {}
    for row in docs:
        row_date = _parse_iso_date(row.get("date"))
        if start and (row_date is None or row_date < start):
            continue
        if end and (row_date is None or row_date > end):
            continue
        topics = row.get("topics") or []
        if isinstance(topics, list):
            for topic in topics:
                name = str(topic).strip()
                if not name:
                    continue
                counts[name] = counts.get(name, 0) + 1
    return counts


def _lineage_rows(
    db: SQLAlchemySession,
    lineage_id: str,
    min_confidence: Optional[float] = None,
):
    query = (
        db.query(Catalog, Document, Event, Place)
        .join(Document, Document.catalog_id == Catalog.id)
        .join(Event, Event.id == Document.event_id)
        .join(Place, Place.id == Event.place_id)
        .filter(Catalog.lineage_id == lineage_id)
    )
    if min_confidence is not None:
        query = query.filter(Catalog.lineage_confidence >= float(min_confidence))
    return query.order_by(Event.record_date.desc(), Catalog.id.desc()).all()


def _semantic_candidate_matches_filters(meta: dict, filters: dict) -> bool:
    result_type = str(meta.get("result_type") or "")
    if not filters.get("include_agenda_items") and result_type != "meeting":
        return False
    city = filters.get("city")
    if city and str(meta.get("city") or "").lower() != str(city).lower():
        return False
    meeting_type = filters.get("meeting_type")
    if meeting_type and str(meta.get("meeting_category") or "").lower() != str(meeting_type).lower():
        return False
    org = filters.get("org")
    if org and str(meta.get("organization") or "").lower() != str(org).lower():
        return False
    date_val = str(meta.get("date") or "")
    date_from = filters.get("date_from")
    date_to = filters.get("date_to")
    if date_from and (not date_val or date_val < date_from):
        return False
    if date_to and (not date_val or date_val > date_to):
        return False
    return True


def _dedupe_semantic_candidates(candidates):
    """
    Deduplicate by parent meeting (`catalog_id`) before pagination.
    Without this, one meeting with many chunk vectors can starve other results.
    """
    best_by_key = {}
    for cand in candidates:
        meta = cand.metadata
        result_type = str(meta.get("result_type") or "meeting")
        if result_type == "meeting":
            key = ("meeting", int(meta.get("catalog_id") or 0))
        else:
            key = ("agenda_item", int(meta.get("db_id") or 0))
        existing = best_by_key.get(key)
        if existing is None or cand.score > existing.score:
            best_by_key[key] = cand
    deduped = list(best_by_key.values())
    deduped.sort(key=lambda c: c.score, reverse=True)
    return deduped


@app.get("/health")
def health_check(db: SQLAlchemySession = Depends(get_db)):
    """
    Deep Health Check: Verifies DB connectivity.
    Used by Docker/Kubernetes to restart the container if it hangs.
    """
    try:
        # 1. Check Database
        db.execute(text("SELECT 1"))
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Database unreachable")

@app.get("/search")
def search_documents(
    q: str = Query(..., min_length=1, description="The search query (e.g., 'zoning')"),
    semantic: bool = Query(False, description="Enable semantic rerank (hybrid lexical + vector)"),
    city: Optional[str] = Query(None),
    include_agenda_items: bool = Query(False, description="Include individual agenda items in search hits"),
    sort: Optional[str] = Query(None, description="Sort mode: newest|oldest|relevance"),
    meeting_type: Optional[str] = Query(None),
    org: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100), # Security: Enforce min/max limits
    offset: int = Query(0, ge=0),
):
    """
    Search for text within meeting minutes using Meilisearch.
    """
    # VALIDATION: Strict Date Checks
    if date_from: validate_date_format(date_from)
    if date_to: validate_date_format(date_to)

    if semantic:
        if not is_db_ready():
            raise HTTPException(status_code=503, detail="Database service is unavailable")
        db = SessionLocal()
        try:
            return search_documents_semantic(
                q=q,
                city=city,
                include_agenda_items=include_agenda_items,
                meeting_type=meeting_type,
                org=org,
                date_from=date_from,
                date_to=date_to,
                limit=limit,
                offset=offset,
                db=db,
            )
        finally:
            db.close()

    try:
        index = client.index('documents')
        
        search_params = {
            'limit': limit,
            'offset': offset,
            'attributesToRetrieve': [
                'id', 'title', 'event_name', 'city', 'date', 'filename', 'url',
                'result_type', 'event_id', 'catalog_id', 'classification', 'result',
                'summary', 'summary_extractive', 'entities', 'topics', 'related_ids',
                'summary_is_stale', 'topics_is_stale',
                'people_metadata',
            ],
            'attributesToCrop': ['content', 'description'],
            'cropLength': 50,
            'attributesToHighlight': ['content', 'title', 'description'],
            'highlightPreTag': '<em class="bg-yellow-200 not-italic font-semibold px-0.5 rounded">',
            'highlightPostTag': '</em>',
            'filter': []
        }

        # Back-compat: when sort is omitted, Meilisearch uses relevance ranking.
        # UI defaults to "newest" by explicitly setting sort=newest.
        if sort is not None:
            sort_mode = (sort or "").strip().lower()
            if sort_mode in {"", "relevance"}:
                pass
            elif sort_mode == "newest":
                search_params["sort"] = ["date:desc"]
            elif sort_mode == "oldest":
                search_params["sort"] = ["date:asc"]
            else:
                raise HTTPException(status_code=400, detail="Invalid sort mode. Use newest|oldest|relevance.")
        
        search_params['filter'] = _build_meilisearch_filter_clauses(
            city=city,
            meeting_type=meeting_type,
            org=org,
            date_from=date_from,
            date_to=date_to,
            include_agenda_items=include_agenda_items,
        )

        if not search_params['filter']:
            del search_params['filter']

        try:
            results = index.search(q, search_params)
        except MeilisearchTimeoutError as e:
            logger.error(f"Search failed (Meilisearch timeout): {e}")
            raise HTTPException(status_code=503, detail="Search engine timed out")
        except MeilisearchCommunicationError as e:
            logger.error(f"Search failed (Meilisearch unavailable): {e}")
            raise HTTPException(status_code=503, detail="Search engine unavailable")
        except MeilisearchError as e:
            # Actionable error: Meilisearch rejects sorting/filtering if index settings don't allow it.
            msg = str(e)
            lowered = msg.lower()
            if "sort" in lowered and ("sortable" in lowered or "attribute" in lowered):
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Meilisearch is not configured to sort by `date`. "
                        "Run `docker compose run --rm pipeline python reindex_only.py` and retry."
                    ),
                )
            logger.error(f"Search failed (Meilisearch error): {e}")
            raise HTTPException(status_code=500, detail="Internal search engine error")
        
        # Performance: Truncate people_metadata to top 10 to keep response size under control
        for hit in results['hits']:
            if 'people_metadata' in hit and isinstance(hit['people_metadata'], list):
                hit['people_metadata'] = hit['people_metadata'][:10]
            if '_formatted' in hit and 'people_metadata' in hit['_formatted'] and isinstance(hit['_formatted']['people_metadata'], list):
                hit['_formatted']['people_metadata'] = hit['_formatted']['people_metadata'][:10]
                
        logger.info(f"Search query='{q}' city='{city}' returned {len(results['hits'])} hits")
        return results
    except HTTPException:
        # Bubble up explicit request validation errors (e.g., bad sort mode).
        raise
    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail="Internal search engine error")


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


@app.get("/search/semantic")
def search_documents_semantic(
    q: str = Query(..., min_length=1, description="The semantic search query (e.g., 'housing density')"),
    city: Optional[str] = Query(None),
    include_agenda_items: bool = Query(False, description="Include individual agenda items in search hits"),
    meeting_type: Optional[str] = Query(None),
    org: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: SQLAlchemySession = Depends(get_db),
):
    """
    Semantic search endpoint.
    B2 uses hybrid retrieval for pgvector (lexical recall + vector rerank).
    Legacy FAISS backend keeps direct semantic query behavior during transition.
    """
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

        # B2 path: hybrid retrieval for pgvector (lexical recall -> vector rerank).
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
            candidates = backend.rerank_candidates(db, q, lexical_hits, top_k=k)
            filtered = [c for c in candidates if _semantic_candidate_matches_filters(c.metadata, filters)]
            filtered_count = len(filtered)
            deduped = _dedupe_semantic_candidates(filtered)
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
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=503,
            detail=(
                "Semantic index artifacts are missing. "
                "Run `docker compose run --rm pipeline python reindex_semantic.py` and retry."
            ),
        ) from e
    except SemanticConfigError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except MeilisearchError as e:
        raise HTTPException(status_code=503, detail=f"Hybrid recall failed: {e}") from e
    except Exception as e:
        logger.error(f"Semantic search failed: {e}")
        raise HTTPException(status_code=500, detail="Internal semantic search error")

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
        if result_type == "meeting":
            hit = meeting_by_db.get(db_id)
        else:
            hit = agenda_by_db.get(db_id)
        if hit:
            hits.append(hit)
    elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
    backend_health = backend.health()
    engine = backend_health.get("engine")
    logger.info(
        "semantic_search query='%s' raw=%s filtered=%s dedup=%s returned=%s k=%s steps=%s latency_ms=%s",
        q,
        raw_count,
        filtered_count,
        len(deduped),
        len(hits),
        k,
        expansion_steps,
        elapsed_ms,
    )
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
            # Exposing engine here makes "semantic feels slow" debuggable from one API response.
            "engine": engine,
        },
    }

@app.get("/metadata")
@cached(expire=3600, key_prefix="metadata") # PERFORMANCE: Cache for 1 hour
def get_metadata():
    """
    Returns unique cities and organizations present in the search index.
    """
    try:
        index = client.index('documents')
        res = index.search("", {
            "facets": ["city", "organization", "meeting_category"],
            "limit": 0
        })
        
        facets = res.get('facetDistribution', {})
        cities = sorted([c.replace("ca_", "").replace("_", " ").title() for c in facets.get('city', {}).keys()])
        orgs = sorted(list(facets.get('organization', {}).keys()))
        types = sorted(list(facets.get('meeting_category', {}).keys()))
        
        return {
            "cities": cities,
            "organizations": orgs,
            "meeting_types": types
        }
    except Exception as e:
        logger.error(f"Metadata retrieval failed: {e}")
        return {"cities": [], "organizations": [], "meeting_types": []}


@app.get("/trends/topics")
@limiter.limit("60/minute")
def get_trends_topics(
    request: Request,
    city: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    limit: int = Query(10, ge=1, le=50),
):
    _ = request
    _require_trends_feature()
    if date_from:
        validate_date_format(date_from)
    if date_to:
        validate_date_format(date_to)
    if date_from or date_to:
        docs = _collect_meeting_docs(city=city)
        topic_counts = _count_topics_from_docs(docs, date_from=date_from, date_to=date_to)
    else:
        topic_counts = _facet_topics(city=city, date_from=date_from, date_to=date_to)
    rows = sorted(topic_counts.items(), key=lambda kv: (-int(kv[1]), str(kv[0]).lower()))[:limit]
    return {
        "city": normalize_city_filter(city) if city else None,
        "date_from": date_from,
        "date_to": date_to,
        "items": [{"topic": topic, "count": int(count)} for topic, count in rows],
    }


@app.get("/trends/compare")
@limiter.limit("30/minute")
def get_trends_compare(
    request: Request,
    cities: List[str] = Query(...),
    date_from: str = Query(...),
    date_to: str = Query(...),
    granularity: str = Query("month", pattern="^(month|quarter)$"),
    limit: int = Query(5, ge=1, le=20),
):
    _ = request
    _require_trends_feature()
    validate_date_format(date_from)
    validate_date_format(date_to)
    start = datetime.strptime(date_from, "%Y-%m-%d").date()
    end = datetime.strptime(date_to, "%Y-%m-%d").date()
    if end < start:
        raise HTTPException(status_code=400, detail="date_to must be >= date_from")
    if len(cities) < 2:
        raise HTTPException(status_code=400, detail="Provide at least two cities")

    normalized_cities = [normalize_city_filter(c) for c in cities]
    buckets = _iter_time_buckets(start=start, end=end, granularity=granularity)

    docs_by_city = {city: _collect_meeting_docs(city=city) for city in normalized_cities}

    # Discover shared high-signal topics first to keep comparison compact.
    pooled: dict[str, int] = {}
    for city, docs in docs_by_city.items():
        counts = _count_topics_from_docs(docs, date_from=date_from, date_to=date_to)
        for topic, count in counts.items():
            pooled[topic] = pooled.get(topic, 0) + int(count)
    top_topics = [name for name, _ in sorted(pooled.items(), key=lambda kv: (-kv[1], kv[0].lower()))[:limit]]

    series = []
    for city in normalized_cities:
        docs = docs_by_city.get(city, [])
        for bucket_start, bucket_end in buckets:
            counts = _count_topics_from_docs(
                docs,
                date_from=bucket_start.isoformat(),
                date_to=bucket_end.isoformat(),
            )
            series.append(
                {
                    "city": city,
                    "bucket": bucket_start.isoformat(),
                    "topics": {topic: int(counts.get(topic, 0)) for topic in top_topics},
                }
            )
    return {
        "granularity": granularity,
        "date_from": date_from,
        "date_to": date_to,
        "topics": top_topics,
        "series": series,
    }


@app.get("/trends/export")
@limiter.limit("10/minute")
def export_trends(
    request: Request,
    city: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    format: str = Query("json", pattern="^(json|csv)$"),
    limit: int = Query(50, ge=1, le=500),
):
    _ = request
    _require_trends_feature()
    if date_from:
        validate_date_format(date_from)
    if date_to:
        validate_date_format(date_to)
    if date_from or date_to:
        docs = _collect_meeting_docs(city=city)
        topic_counts = _count_topics_from_docs(docs, date_from=date_from, date_to=date_to)
    else:
        topic_counts = _facet_topics(city=city, date_from=date_from, date_to=date_to)
    rows = sorted(topic_counts.items(), key=lambda kv: (-int(kv[1]), str(kv[0]).lower()))[:limit]

    if format == "csv":
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["topic", "count", "city", "date_from", "date_to"])
        normalized_city = normalize_city_filter(city) if city else ""
        for topic, count in rows:
            writer.writerow([topic, int(count), normalized_city, date_from or "", date_to or ""])
        return Response(content=buffer.getvalue(), media_type="text/csv")

    return {
        "city": normalize_city_filter(city) if city else None,
        "date_from": date_from,
        "date_to": date_to,
        "items": [{"topic": topic, "count": int(count)} for topic, count in rows],
    }


@app.get("/lineage/{lineage_id}")
@limiter.limit("60/minute")
def get_lineage(
    request: Request,
    lineage_id: str,
    min_confidence: Optional[float] = Query(None, ge=0.0, le=1.0),
    db: SQLAlchemySession = Depends(get_db),
):
    _ = request
    _require_trends_feature()
    rows = _lineage_rows(db, lineage_id=lineage_id, min_confidence=min_confidence)
    if not rows:
        raise HTTPException(status_code=404, detail="Lineage not found")
    meetings = []
    for catalog, _doc, event, place in rows:
        meetings.append(
            {
                "catalog_id": catalog.id,
                "lineage_id": catalog.lineage_id,
                "lineage_confidence": float(catalog.lineage_confidence or 0.0),
                "lineage_updated_at": catalog.lineage_updated_at.isoformat() if catalog.lineage_updated_at else None,
                "event_name": event.name,
                "date": event.record_date.isoformat() if event.record_date else None,
                "city": place.display_name or place.name,
                "summary": catalog.summary,
            }
        )
    return {"lineage_id": lineage_id, "count": len(meetings), "meetings": meetings}


@app.get("/catalog/{catalog_id}/lineage")
@limiter.limit("60/minute")
def get_catalog_lineage(
    request: Request,
    catalog_id: int = Path(..., ge=1),
    min_confidence: Optional[float] = Query(None, ge=0.0, le=1.0),
    db: SQLAlchemySession = Depends(get_db),
):
    _ = request
    _require_trends_feature()
    catalog = db.get(Catalog, catalog_id)
    if not catalog:
        raise HTTPException(status_code=404, detail="Catalog not found")
    if not catalog.lineage_id:
        return {
            "catalog_id": catalog_id,
            "lineage_id": None,
            "count": 0,
            "meetings": [],
        }
    rows = _lineage_rows(db, lineage_id=catalog.lineage_id, min_confidence=min_confidence)
    meetings = []
    for c_row, _doc, event, place in rows:
        meetings.append(
            {
                "catalog_id": c_row.id,
                "lineage_confidence": float(c_row.lineage_confidence or 0.0),
                "date": event.record_date.isoformat() if event.record_date else None,
                "event_name": event.name,
                "city": place.display_name or place.name,
            }
        )
    return {
        "catalog_id": catalog_id,
        "lineage_id": catalog.lineage_id,
        "lineage_confidence": float(catalog.lineage_confidence or 0.0),
        "count": len(meetings),
        "meetings": meetings,
    }

@app.get("/people")
def list_people(
    limit: int = Query(50, ge=1, le=200), # PERFORMANCE: Enforce limits to prevent OOM
    offset: int = Query(0, ge=0),
    include_mentions: bool = Query(False, description="Include mention-only names for diagnostics"),
    db: SQLAlchemySession = Depends(get_db)
):
    """
    Returns a paginated list of identified officials.
    """
    try:
        # By default we return official profiles only.
        # Mention-only names are available via include_mentions=true for diagnostics.
        base_query = db.query(Person)
        if not include_mentions:
            base_query = base_query.filter(Person.person_type == "official")

        # PERFORMANCE: Return total count for frontend pagination logic
        total = base_query.count()
        people = base_query.order_by(Person.name).limit(limit).offset(offset).all()
        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "include_mentions": include_mentions,
            "results": people
        }
    except Exception as e:
        logger.error(f"Failed to list people: {e}")
        raise HTTPException(status_code=500, detail="Database error")

@app.get("/person/{person_id}")
def get_person_history(
    person_id: int = Path(..., ge=1), 
    db: SQLAlchemySession = Depends(get_db)
):
    """
    Returns a person's full profile and roles.
    """
    # PERFORMANCE: Eager Loading
    # Instead of asking the database 30 separate questions ("Who is this?", "What city?", "What role?"),
    # we ask ONE big question ("Give me everything about this person at once").
    # This makes the profile page load instantly (1 query vs 31 queries).
    person = db.query(Person).options(
        joinedload(Person.memberships)
        .joinedload(Membership.organization)
        .joinedload(Organization.place)
    ).filter(Person.id == person_id).first()

    if not person:
        raise HTTPException(status_code=404, detail="Official not found")
    
    history = []
    for membership in person.memberships:
        history.append({
            "body": membership.organization.name,
            "city": membership.organization.place.name.title(),
            "role": membership.label or "Member"
        })
        
    return {
        "name": person.name,
        "bio": person.biography,
        "current_role": person.current_role,
        "roles": history
    }

@app.get("/catalog/batch")
def get_catalogs_batch(
    ids: List[int] = Query(...),
    db: SQLAlchemySession = Depends(get_db)
):
    """
    Returns a list of meeting summaries for multiple IDs.
    Used to display 'Related Meetings' links.
    """
    # SECURITY: Limit the number of IDs requested to prevent database exhaustion.
    if len(ids) > 50:
        raise HTTPException(status_code=400, detail="Batch request too large. Limit is 50 IDs.")

    records = db.query(Catalog, Document, Event, Place).join(
        Document, Document.catalog_id == Catalog.id
    ).join(
        Event, Document.event_id == Event.id
    ).join(
        Place, Document.place_id == Place.id
    ).filter(Catalog.id.in_(ids)).all()

    
    results = []
    for cat, doc, event, place in records:
        results.append({
            "id": cat.id,
            "filename": cat.filename,
            "title": event.name,
            "date": event.record_date.isoformat() if event.record_date else None,
            "city": place.display_name or place.name
        })
    return results

from pipeline.tasks import (
    generate_summary_task,
    generate_topics_task,
    segment_agenda_task,
    extract_votes_task,
    extract_text_task,
    app as celery_app,
)
from celery.result import AsyncResult
@app.post("/summarize/{catalog_id}", dependencies=[Depends(verify_api_key)])
@limiter.limit("20/minute") # Higher limit since it's non-blocking
def summarize_document(
    request: Request,
    catalog_id: int = Path(..., ge=1),
    force: bool = Query(
        False,
        description=(
            "Force regeneration even if a cached summary exists. "
            "Useful after summarization logic changes or when cached data is known-bad."
        ),
    ),
    db: SQLAlchemySession = Depends(get_db)
):
    """
    Async AI: Requests a summary generation.
    Returns a 'Task ID' immediately. Use GET /tasks/{id} to check progress.
    """
    catalog = db.get(Catalog, catalog_id)
    if not catalog:
        raise HTTPException(status_code=404, detail="Document not found")
    if not catalog.content:
        raise HTTPException(status_code=400, detail="Document has no text to summarize")

    # Block generation when extracted text is too weak to support reliable output.
    quality = analyze_source_text(catalog.content)
    if not is_source_summarizable(quality):
        return {
            "status": "blocked_low_signal",
            "reason": build_low_signal_message(quality),
        }

    # "Cached" should mean: generated from the *current* extracted text.
    # If extracted text changed (re-extraction), we keep the old summary but mark it stale.
    content_hash = catalog.content_hash or (compute_content_hash(catalog.content) if catalog.content else None)
    is_fresh = bool(
        catalog.summary
        and content_hash
        and catalog.summary_source_hash
        and catalog.summary_source_hash == content_hash
    )

    if (not force) and is_fresh:
        return {"summary": catalog.summary, "status": "cached"}
    if (not force) and catalog.summary and not is_fresh:
        return {"summary": catalog.summary, "status": "stale"}

    # THE 'MAILBOX' (Celery):
    # We don't make the user wait while the AI writes a summary.
    # Instead, we put a 'task' in the mailbox and tell the user: 
    # "We're on it! Here is your tracking number."
    task = generate_summary_task.delay(catalog_id, force=force)
    
    return {
        "status": "processing",
        "task_id": str(task.id),
        "poll_url": f"/tasks/{task.id}"
    }

@app.post("/segment/{catalog_id}", dependencies=[Depends(verify_api_key)])
@limiter.limit("20/minute")
def segment_agenda(
    request: Request,
    catalog_id: int = Path(..., ge=1),
    force: bool = Query(
        False,
        description=(
            "Force regeneration even if cached items exist. "
            "Useful after segmentation logic changes or when cached data is known-bad."
        ),
    ),
    db: SQLAlchemySession = Depends(get_db)
):
    """
    Async AI: Requests agenda segmentation.
    Returns a 'Task ID' immediately.
    """
    catalog = db.get(Catalog, catalog_id)
    if not catalog:
        raise HTTPException(status_code=404, detail="Document not found")

    # Check cache
    existing_items = db.query(AgendaItem).filter_by(catalog_id=catalog_id).order_by(AgendaItem.order).all()
    # The resolver may evolve over time. When it does, we sometimes need a way to
    # refresh previously cached agenda rows. `force=true` is that escape hatch.
    if not force and existing_items and agenda_items_look_low_quality and not agenda_items_look_low_quality(existing_items):
        return {"status": "cached", "items": existing_items}
    if not force and existing_items:
        logger.info(
            f"Agenda cache for catalog_id={catalog_id} looks low quality; regenerating asynchronously."
        )
    if force:
        logger.info(f"Force-regenerating agenda cache for catalog_id={catalog_id}.")

    # Dispatch Task
    task = segment_agenda_task.delay(catalog_id)
    
    return {
        "status": "processing",
        "task_id": str(task.id),
        "poll_url": f"/tasks/{task.id}"
    }


@app.post("/votes/{catalog_id}", dependencies=[Depends(verify_api_key)])
@limiter.limit("20/minute")
def extract_votes(
    request: Request,
    catalog_id: int = Path(..., ge=1),
    force: bool = Query(
        False,
        description=(
            "Force vote extraction even when the feature flag is disabled or items already have "
            "high-confidence LLM vote data."
        ),
    ),
    db: SQLAlchemySession = Depends(get_db),
):
    """
    Async AI: Requests vote/outcome extraction for segmented agenda items.
    Returns a Task ID immediately.
    """
    catalog = db.get(Catalog, catalog_id)
    if not catalog:
        raise HTTPException(status_code=404, detail="Document not found")

    task = extract_votes_task.delay(catalog_id, force=force)
    return {
        "status": "processing",
        "task_id": str(task.id),
        "poll_url": f"/tasks/{task.id}",
    }


@app.get("/catalog/{catalog_id}/content", dependencies=[Depends(verify_api_key)])
def get_catalog_content(
    catalog_id: int = Path(..., ge=1),
    db: SQLAlchemySession = Depends(get_db),
):
    """
    Return the raw extracted text for one catalog.

    This is primarily used by the UI after a re-extraction so the user can see
    updated text immediately (even before search reindexing completes).
    """
    catalog = db.get(Catalog, catalog_id)
    if not catalog:
        raise HTTPException(status_code=404, detail="Document not found")
    if not catalog.content:
        return {"catalog_id": catalog_id, "chars": 0, "content": ""}
    return {
        "catalog_id": catalog_id,
        "chars": len(catalog.content),
        "has_page_markers": "[PAGE " in catalog.content,
        "content": catalog.content,
    }


@app.get("/catalog/{catalog_id}/derived_status", dependencies=[Depends(verify_api_key)])
def get_catalog_derived_status(
    catalog_id: int = Path(..., ge=1),
    db: SQLAlchemySession = Depends(get_db),
):
    """
    Return whether derived fields (summary/topics) are stale for the current extracted text.

    This endpoint is used by the UI to show a clear "stale" badge after re-extraction,
    without auto-regenerating anything.
    """
    catalog = db.get(Catalog, catalog_id)
    if not catalog:
        raise HTTPException(status_code=404, detail="Document not found")

    content_hash = catalog.content_hash or (compute_content_hash(catalog.content) if catalog.content else None)
    summary_is_stale = bool(
        catalog.summary and (not content_hash or catalog.summary_source_hash != content_hash)
    )
    topics_is_stale = bool(
        catalog.topics is not None and (not content_hash or catalog.topics_source_hash != content_hash)
    )
    agenda_segmentation_status = getattr(catalog, "agenda_segmentation_status", None)
    agenda_segmentation_attempted_at = getattr(catalog, "agenda_segmentation_attempted_at", None)
    agenda_segmentation_item_count = getattr(catalog, "agenda_segmentation_item_count", None)
    agenda_segmentation_error = getattr(catalog, "agenda_segmentation_error", None)

    valid_segmentation_statuses = {None, "complete", "empty", "failed"}
    if agenda_segmentation_status not in valid_segmentation_statuses:
        agenda_segmentation_status = None

    # Prefer the catalog-level count if present (avoids extra queries when possible).
    if isinstance(agenda_segmentation_item_count, int):
        agenda_items_count = agenda_segmentation_item_count
    else:
        agenda_items_count = db.query(AgendaItem).filter(AgendaItem.catalog_id == catalog_id).count()
    quality = analyze_source_text(catalog.content or "")
    summary_blocked_reason = None
    topics_blocked_reason = None
    has_content = bool(catalog.content and catalog.content.strip())
    if has_content:
        if not is_source_summarizable(quality):
            summary_blocked_reason = build_low_signal_message(quality)
        if not is_source_topicable(quality):
            topics_blocked_reason = build_low_signal_message(quality)

    has_topics = catalog.topics is not None
    has_topic_values = bool(catalog.topics is not None and len(catalog.topics or []) > 0)
    summary_not_generated_yet = bool(has_content and not catalog.summary and not summary_blocked_reason)
    topics_not_generated_yet = bool(has_content and not has_topic_values and not topics_blocked_reason)
    # Agenda segmentation is a separate derived process. We treat "0 items" as:
    # - not_generated_yet: never attempted
    # - empty: attempted but found no substantive items
    agenda_not_generated_yet = bool(has_content and agenda_segmentation_status is None)
    agenda_is_empty = bool(has_content and agenda_segmentation_status == "empty")

    return {
        "catalog_id": catalog_id,
        "has_content": has_content,
        "content_hash": content_hash,
        "has_summary": bool(catalog.summary),
        "summary_source_hash": catalog.summary_source_hash,
        "summary_is_stale": summary_is_stale,
        "summary_blocked_reason": summary_blocked_reason,
        "summary_not_generated_yet": summary_not_generated_yet,
        "has_topics": has_topics,
        "topics_source_hash": catalog.topics_source_hash,
        "topics_is_stale": topics_is_stale,
        "topics_blocked_reason": topics_blocked_reason,
        "topics_not_generated_yet": topics_not_generated_yet,
        "agenda_items_count": agenda_items_count,
        "agenda_not_generated_yet": agenda_not_generated_yet,
        "agenda_is_empty": agenda_is_empty,
        "agenda_segmentation_status": agenda_segmentation_status,
        "agenda_segmentation_attempted_at": agenda_segmentation_attempted_at.isoformat() if agenda_segmentation_attempted_at else None,
        "agenda_segmentation_item_count": agenda_segmentation_item_count,
        "agenda_segmentation_error": agenda_segmentation_error,
    }


@app.post("/topics/{catalog_id}", dependencies=[Depends(verify_api_key)])
@limiter.limit("10/minute")
def generate_topics_for_catalog(
    request: Request,
    catalog_id: int = Path(..., ge=1),
    force: bool = Query(
        False,
        description=(
            "Force regeneration even if cached topics exist. "
            "Useful after extraction changes or when cached topics are known-bad."
        ),
    ),
    db: SQLAlchemySession = Depends(get_db),
):
    """
    Async topic tagging: requests topic generation for one catalog.

    We keep regeneration explicit (no automatic re-tagging after extraction),
    but we also avoid serving "cached" topics when they are stale.
    """
    catalog = db.get(Catalog, catalog_id)
    if not catalog:
        raise HTTPException(status_code=404, detail="Document not found")

    if not catalog.content:
        raise HTTPException(status_code=400, detail="Document has no text to tag")

    quality = analyze_source_text(catalog.content)
    if not is_source_topicable(quality):
        return {
            "status": "blocked_low_signal",
            "reason": build_low_signal_message(quality),
            "topics": [],
        }

    content_hash = catalog.content_hash or (compute_content_hash(catalog.content) if catalog.content else None)
    is_fresh = bool(
        catalog.topics is not None
        and content_hash
        and catalog.topics_source_hash
        and catalog.topics_source_hash == content_hash
    )
    if (not force) and is_fresh:
        return {"status": "cached", "topics": catalog.topics or []}
    if (not force) and catalog.topics is not None and not is_fresh:
        return {"status": "stale", "topics": catalog.topics or []}

    task = generate_topics_task.delay(catalog_id, force=force)
    return {
        "status": "processing",
        "task_id": str(task.id),
        "poll_url": f"/tasks/{task.id}",
    }


@app.post("/extract/{catalog_id}", dependencies=[Depends(verify_api_key)])
@limiter.limit("5/minute")
def extract_catalog_text(
    request: Request,
    catalog_id: int = Path(..., ge=1),
    force: bool = Query(
        False,
        description="Force re-extraction even if cached extracted text exists.",
    ),
    ocr_fallback: bool = Query(
        False,
        description="Allow OCR fallback when the PDF has little/no selectable text (slower).",
    ),
    db: SQLAlchemySession = Depends(get_db),
):
    """
    Async extraction: re-extract one catalog's text from its already-downloaded file.

    We do not download here. If the file isn't present on disk, the task fails fast.
    """
    catalog = db.get(Catalog, catalog_id)
    if not catalog:
        raise HTTPException(status_code=404, detail="Document not found")

    # Cheap cache: if we already have substantial text, don't re-extract unless forced.
    if (not force) and catalog.content and len(catalog.content.strip()) >= 800:
        return {"status": "cached", "catalog_id": catalog_id, "chars": len(catalog.content)}

    task = extract_text_task.delay(catalog_id, force=force, ocr_fallback=ocr_fallback)
    return {
        "status": "processing",
        "task_id": str(task.id),
        "poll_url": f"/tasks/{task.id}",
    }

@app.get("/tasks/{task_id}")
def get_task_status(task_id: str):
    """
    Check the status of a background AI task.
    """
    task = AsyncResult(task_id, app=celery_app)
    
    if task.ready():
        result = task.result
        # Handle errors propagated from the worker
        if isinstance(result, Exception):
            return {"status": "failed", "error": str(result)}
        elif isinstance(result, dict) and "error" in result:
            return {"status": "failed", "error": result["error"]}
            
        return {
            "status": "complete",
            "result": result
        }
    else:
        return {"status": "processing"}

@app.get("/stats")
def get_stats():
    """
    Returns basic statistics about the search index.
    """
    try:
        return client.index('documents').get_stats()
    except Exception as e:
        logger.error(f"Stats check failed: {e}")
        raise HTTPException(status_code=503, detail="Search engine unreachable")

# --------------------------------------------------------------------------
# DATA QUALITY REPORTING (FEEDBACK LOOP)
# --------------------------------------------------------------------------

class IssueReport(BaseModel):
    """
    Schema for the data quality report submitted by the user.
    """
    event_id: int = Field(..., description="The ID of the meeting being reported")
    issue_type: str = Field(..., description="The type of problem (e.g., 'broken_link')")
    description: Optional[str] = Field(None, max_length=500, description="Optional details about the issue")

@app.post("/report-issue", dependencies=[Depends(verify_api_key)])
@limiter.limit("5/minute")
def report_data_issue(request: Request, report: IssueReport, db: SQLAlchemySession = Depends(get_db)):
    """
    Allows users to report errors in the data (e.g., broken links, OCR errors).
    
    Novice Developer Note:
    This function validates the report, checks if the meeting actually exists,
    and then saves the report to the 'data_issue' table for an admin to review.
    """
    # 1. Validation: Does the meeting actually exist in our database?
    event = db.query(Event).filter(Event.id == report.event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Meeting not found")

    # 2. Validation: Is the issue type one we recognize?
    valid_types = [t.value for t in IssueType]
    if report.issue_type not in valid_types:
        raise HTTPException(status_code=400, detail=f"Invalid issue_type. Must be one of: {valid_types}")

    # 3. Save the report
    try:
        new_issue = DataIssue(
            event_id=report.event_id,
            issue_type=report.issue_type,
            description=report.description
        )
        db.add(new_issue)
        db.commit()
        
        logger.info(f"User reported an issue for event {report.event_id}: {report.issue_type}")
        return {"status": "success", "message": "Thank you for your report. Our team will review it."}
        
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to save data issue: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while saving report")

import logging
import os
import sys
from contextlib import asynccontextmanager
from typing import Any, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Path, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as SQLAlchemySession, joinedload
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text
from slowapi import _rate_limit_exceeded_handler

from api import app_setup
from api.app_setup import SEMANTIC_SERVICE_URL as SEMANTIC_SERVICE_URL
from api.catalog_routes import (
    _summary_doc_kind_and_hashes as _summary_doc_kind_and_hashes,
    build_catalog_router,
)
from api.search_routes import (
    MEILI_HOST as MEILI_HOST,
    MEILI_MASTER_KEY as MEILI_MASTER_KEY,
    _build_filter_values as _build_filter_values,
    _build_meilisearch_filter_clauses as _build_meilisearch_filter_clauses,
    _collect_meeting_docs as _collect_meeting_docs,
    _count_topics_from_docs as _count_topics_from_docs,
    _facet_topics as _facet_topics,
    _iter_time_buckets as _iter_time_buckets,
    _normalize_city_or_400 as _normalize_city_or_400,
    _normalize_filters_or_400 as _normalize_filters_or_400,
    _parse_iso_date as _parse_iso_date,
    _require_trends_feature as _require_trends_feature,
    _semantic_service_get_json as _semantic_service_get_json,
    _semantic_service_healthcheck as _semantic_service_healthcheck,
    client as client,
    normalize_city_filter as normalize_city_filter,
    router as search_router,
    search_documents as search_documents,
    search_documents_semantic as search_documents_semantic,
    validate_date_format as validate_date_format,
)
from api.task_routes import (
    AsyncResult as AsyncResult,
    _CeleryTaskProxy as _CeleryTaskProxy,
    _enqueue_task as _enqueue_task,
    build_task_router,
    extract_text_task as extract_text_task,
    extract_votes_task as extract_votes_task,
    generate_summary_task as generate_summary_task,
    generate_topics_task as generate_topics_task,
    segment_agenda_task as segment_agenda_task,
)
from pipeline.config import (
    SEMANTIC_ENABLED as SEMANTIC_ENABLED,
    FEATURE_TRENDS_DASHBOARD as FEATURE_TRENDS_DASHBOARD,
)

# Metrics are internal-only and are scraped by Prometheus from the Docker network.
from api.metrics import instrument_app

# Set up structured logging for production observability
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("town-council-api")

limiter = app_setup.limiter
hmac = app_setup.hmac
sessionmaker = app_setup.sessionmaker
db_connect = app_setup.db_connect
SessionLocal = app_setup.SessionLocal
_db_init_error = app_setup._db_init_error

agenda_items_look_low_quality = None

from pipeline.models import AgendaItem as AgendaItem  # noqa: F401
from pipeline.models import Catalog, DataIssue, Document, Event, IssueType, Membership, Organization, Person, Place
from pipeline.agenda_resolver import agenda_items_look_low_quality as agenda_items_look_low_quality


def _sync_app_setup_from_facade() -> None:
    app_setup.SessionLocal = SessionLocal
    app_setup._db_init_error = _db_init_error
    app_setup.db_connect = db_connect
    app_setup.sessionmaker = sessionmaker


def _sync_facade_from_app_setup() -> None:
    globals()["SessionLocal"] = app_setup.SessionLocal
    globals()["_db_init_error"] = app_setup._db_init_error


def initialize_database() -> Any:
    _sync_app_setup_from_facade()
    try:
        return app_setup.initialize_database()
    finally:
        _sync_facade_from_app_setup()


def is_db_ready() -> bool:
    _sync_app_setup_from_facade()
    try:
        return app_setup.is_db_ready()
    finally:
        _sync_facade_from_app_setup()


def get_db():
    _sync_app_setup_from_facade()
    try:
        yield from app_setup.get_db()
    finally:
        _sync_facade_from_app_setup()


async def verify_api_key(request: Request, x_api_key: str = Header(None)):
    return await app_setup.verify_api_key(request, x_api_key=x_api_key)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _sync_app_setup_from_facade()
    async with app_setup.lifespan(app):
        _sync_facade_from_app_setup()
        yield
    _sync_facade_from_app_setup()


app = FastAPI(
    title="Town Council Search API", 
    description="Search and retrieve local government meeting minutes.",
    default_response_class=ORJSONResponse,
    lifespan=lifespan,
)

# Add /metrics and request timing counters (route-template labels to avoid cardinality blowups).
instrument_app(app)

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

def get_local_ai():
    """
    Legacy dependency hook preserved for older tests.

    Why this exists:
    The API no longer instantiates the local LLM directly, but several targeted
    tests still import and override this symbol.
    """
    return None

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

@app.get("/")
def read_root():
    return {"status": "ok", "message": "Town Council API is running. Go to /docs for the Swagger UI."}

app.include_router(search_router)
catalog_router = build_catalog_router(
    get_db_dependency=get_db,
    verify_api_key_dependency=verify_api_key,
)
app.include_router(catalog_router)
task_router = build_task_router(
    limiter=limiter,
    get_db_dependency=get_db,
    verify_api_key_dependency=verify_api_key,
    task_facade=sys.modules[__name__],
)
app.include_router(task_router)


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

@app.get("/lineage/{lineage_id}")
@limiter.limit("60/minute")
def get_lineage(
    request: Request,
    lineage_id: str,
    min_confidence: Optional[float] = Query(None, ge=0.0, le=1.0),
    db: SQLAlchemySession = Depends(get_db),
):
    _ = request
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

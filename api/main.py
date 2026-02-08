import sys
import os
import logging
import meilisearch
from fastapi import FastAPI, HTTPException, Query, Path, Depends, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse
from typing import List, Optional
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as SQLAlchemySession, sessionmaker, joinedload
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from api.cache import cached

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
agenda_items_look_low_quality = lambda items: False

try:
    from pipeline.models import db_connect, Document, Event, Place, Catalog, Person, AgendaItem, DataIssue, IssueType, Membership, Organization
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
async def verify_api_key(x_api_key: str = Header(None)):
    expected_key = os.getenv("API_AUTH_KEY", "dev_secret_key_change_me")
    if x_api_key != expected_key:
        # Mask the key in logs to prevent secret leakage (e.g. 'abc***')
        masked_key = f"{x_api_key[:3]}***" if x_api_key else "None"
        logger.warning(f"Unauthorized API access attempt with key: {masked_key}")
        raise HTTPException(status_code=401, detail="Invalid or missing API Key")

# PERFORMANCE: Use ORJSONResponse for 3-5x faster JSON serialization
app = FastAPI(
    title="Town Council Search API", 
    description="Search and retrieve local government meeting minutes.",
    default_response_class=ORJSONResponse
)

# SECURITY: Startup Guardrail
# Warn the administrator if they forgot to change the default secret.
@app.on_event("startup")
async def check_security_config():
    key = os.getenv("API_AUTH_KEY", "dev_secret_key_change_me")
    if key == "dev_secret_key_change_me":
        logger.critical("SECURITY WARNING: You are using the default API Key. Please set API_AUTH_KEY in production.")


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

from sqlalchemy import text
import re

# ... existing imports ...

# Add Date Validation Helper
def validate_date_format(date_str: str):
    """Ensures date is YYYY-MM-DD"""
    if not re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")


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
    city: Optional[str] = Query(None),
    meeting_type: Optional[str] = Query(None),
    org: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100), # Security: Enforce min/max limits
    offset: int = Query(0, ge=0)
):
    """
    Search for text within meeting minutes using Meilisearch.
    """
    # VALIDATION: Strict Date Checks
    if date_from: validate_date_format(date_from)
    if date_to: validate_date_format(date_to)

    try:
        index = client.index('documents')
        
        search_params = {
            'limit': limit,
            'offset': offset,
            'attributesToRetrieve': ['id', 'title', 'event_name', 'city', 'date', 'filename', 'url', 'result_type', 'event_id', 'catalog_id', 'classification', 'result', 'topics', 'people_metadata'],
            'attributesToCrop': ['content', 'description'],
            'cropLength': 50,
            'attributesToHighlight': ['content', 'title', 'description'],
            'highlightPreTag': '<em class="bg-yellow-200 not-italic font-semibold px-0.5 rounded">',
            'highlightPostTag': '</em>',
            'filter': []
        }
        
        # SECURITY: We sanitize inputs by escaping double quotes.
        # This prevents 'Filter Injection' attacks where a user might try to 
        # bypass search logic using malicious query strings.
        def sanitize_filter(val):
            return str(val).replace('"', '\\"')

        # Normalize city to lowercase to match the indexed display_name (e.g., 'ca_berkeley')
        if city: search_params['filter'].append(f'city = "{sanitize_filter(city.lower())}"')
        if meeting_type: search_params['filter'].append(f'meeting_category = "{sanitize_filter(meeting_type)}"')
        if org: search_params['filter'].append(f'organization = "{sanitize_filter(org)}"')

        if date_from and date_to:
            search_params['filter'].append(f'date >= "{sanitize_filter(date_from)}" AND date <= "{sanitize_filter(date_to)}"')
        elif date_from:
            search_params['filter'].append(f'date >= "{sanitize_filter(date_from)}"')
        elif date_to:
            search_params['filter'].append(f'date <= "{sanitize_filter(date_to)}"')

        if not search_params['filter']:
            del search_params['filter']

        results = index.search(q, search_params)
        
        # Performance: Truncate people_metadata to top 10 to keep response size under control
        for hit in results['hits']:
            if 'people_metadata' in hit and isinstance(hit['people_metadata'], list):
                hit['people_metadata'] = hit['people_metadata'][:10]
            if '_formatted' in hit and 'people_metadata' in hit['_formatted'] and isinstance(hit['_formatted']['people_metadata'], list):
                hit['_formatted']['people_metadata'] = hit['_formatted']['people_metadata'][:10]
                
        logger.info(f"Search query='{q}' city='{city}' returned {len(results['hits'])} hits")
        return results
    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail="Internal search engine error")

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

from pipeline.tasks import generate_summary_task, segment_agenda_task, app as celery_app
from celery.result import AsyncResult

@app.post("/summarize/{catalog_id}", dependencies=[Depends(verify_api_key)])
@limiter.limit("20/minute") # Higher limit since it's non-blocking
def summarize_document(
    request: Request,
    catalog_id: int = Path(..., ge=1),
    db: SQLAlchemySession = Depends(get_db)
):
    """
    Async AI: Requests a summary generation.
    Returns a 'Task ID' immediately. Use GET /tasks/{id} to check progress.
    """
    catalog = db.get(Catalog, catalog_id)
    if not catalog:
        raise HTTPException(status_code=404, detail="Document not found")

    # If cached, return immediately
    if catalog.summary:
        return {"summary": catalog.summary, "status": "cached"}

    if not catalog.content:
        raise HTTPException(status_code=400, detail="Document has no text to summarize")

    # THE 'MAILBOX' (Celery):
    # We don't make the user wait while the AI writes a summary.
    # Instead, we put a 'task' in the mailbox and tell the user: 
    # "We're on it! Here is your tracking number."
    task = generate_summary_task.delay(catalog_id)
    
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
    if existing_items and not agenda_items_look_low_quality(existing_items):
        return {"status": "cached", "items": existing_items}
    if existing_items:
        logger.info(
            f"Agenda cache for catalog_id={catalog_id} looks low quality; regenerating asynchronously."
        )

    # Dispatch Task
    task = segment_agenda_task.delay(catalog_id)
    
    return {
        "status": "processing",
        "task_id": str(task.id),
        "poll_url": f"/tasks/{task.id}"
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

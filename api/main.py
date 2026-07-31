import logging
import os
import sys

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse
from sqlalchemy.orm import Session as SQLAlchemySession
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text
from slowapi import _rate_limit_exceeded_handler

from api.app_setup import get_db, lifespan, limiter, verify_api_key
from api.catalog_routes import (
    _summary_doc_kind_and_hashes as _summary_doc_kind_and_hashes,
    build_catalog_router,
)
from api.lineage_routes import _lineage_rows as _lineage_rows
from api.lineage_routes import build_lineage_router
from api.people_routes import build_people_router
from api.reporting_routes import build_reporting_router
from api.search import support_core as search_support_core
from api.search_routes import router as search_router
from api.task_routes import (
    AsyncResult as AsyncResult,
    _enqueue_task as _enqueue_task,
    build_task_router,
    extract_text_task as extract_text_task,
    extract_votes_task as extract_votes_task,
    generate_summary_task as generate_summary_task,
    generate_topics_task as generate_topics_task,
    segment_agenda_task as segment_agenda_task,
)
# Metrics are internal-only and are scraped by Prometheus from the Docker network.
from api.metrics import instrument_app

# Set up structured logging for production observability
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("town-council-api")

from pipeline.agenda_resolver import agenda_items_look_low_quality as agenda_items_look_low_quality


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

# SECURITY: Restrict CORS (Cross-Origin Resource Sharing)
# We load the allowed domains from the environment.
allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
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
lineage_router = build_lineage_router(
    limiter=limiter,
    get_db_dependency=get_db,
    lineage_facade=sys.modules[__name__],
)
app.include_router(lineage_router)
people_router = build_people_router(get_db_dependency=get_db)
app.include_router(people_router)
reporting_router = build_reporting_router(
    limiter=limiter,
    get_db_dependency=get_db,
    verify_api_key_dependency=verify_api_key,
)
app.include_router(reporting_router)
task_router = build_task_router(
    limiter=limiter,
    get_db_dependency=get_db,
    verify_api_key_dependency=verify_api_key,
    task_facade=sys.modules[__name__],
)
app.include_router(task_router)


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

@app.get("/stats")
def get_stats():
    """
    Returns basic statistics about the search index.
    """
    try:
        search_stats = search_support_core.client.index("documents").get_stats()
        return {"number_of_documents": search_stats.number_of_documents}
    except Exception as e:
        logger.error(f"Stats check failed: {e}")
        raise HTTPException(status_code=503, detail="Search engine unreachable")

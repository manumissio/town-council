import logging
import os
import sys
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse
from sqlalchemy.orm import Session as SQLAlchemySession
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text
from slowapi import _rate_limit_exceeded_handler

from api import app_setup
from api.app_setup import SEMANTIC_SERVICE_URL as SEMANTIC_SERVICE_URL
from api.catalog_routes import (
    _summary_doc_kind_and_hashes as _summary_doc_kind_and_hashes,
    build_catalog_router,
)
from api.lineage_routes import _lineage_rows as _lineage_rows
from api.lineage_routes import build_lineage_router
from api.people_routes import build_people_router
from api.reporting_routes import IssueReport as IssueReport
from api.reporting_routes import build_reporting_router
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
from pipeline.models import Catalog as Catalog  # noqa: F401
from pipeline.models import DataIssue as DataIssue  # noqa: F401
from pipeline.models import Document as Document  # noqa: F401
from pipeline.models import Event as Event  # noqa: F401
from pipeline.models import IssueType as IssueType  # noqa: F401
from pipeline.models import Membership as Membership  # noqa: F401
from pipeline.models import Organization as Organization  # noqa: F401
from pipeline.models import Person as Person  # noqa: F401
from pipeline.models import Place as Place  # noqa: F401
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
        return client.index('documents').get_stats()
    except Exception as e:
        logger.error(f"Stats check failed: {e}")
        raise HTTPException(status_code=503, detail="Search engine unreachable")

import hmac
import logging
import os
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from pipeline.config import SEMANTIC_ENABLED
from pipeline.models import db_connect
from pipeline.startup_purge import run_startup_purge_if_enabled

DEFAULT_API_AUTH_KEY = "dev_secret_key_change_me"
DATABASE_UNAVAILABLE_DETAIL = "Database service is unavailable"
SEMANTIC_SERVICE_URL = os.getenv("SEMANTIC_SERVICE_URL", "http://semantic:8010").rstrip("/")

# This protects the local API worker from expensive endpoint floods.
limiter = Limiter(key_func=get_remote_address)

SessionLocal: Any = None
_db_init_error: Exception | None = None


logger = logging.getLogger("town-council-api")


def initialize_database() -> Any:
    global SessionLocal, _db_init_error
    if SessionLocal is not None:
        return SessionLocal
    try:
        engine = db_connect()
        SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        _db_init_error = None
    except (SQLAlchemyError, RuntimeError, OSError) as exc:
        SessionLocal = None
        _db_init_error = exc
        logger.error("CRITICAL: Could not initialize database session factory: %s", exc)
    return SessionLocal


def is_db_ready() -> bool:
    return SessionLocal is not None


def get_db() -> Iterator[Any]:
    initialize_database()
    if not is_db_ready():
        raise HTTPException(status_code=503, detail=DATABASE_UNAVAILABLE_DETAIL)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def verify_api_key(request: Request, x_api_key: str = Header(None)) -> None:
    expected_key = os.getenv("API_AUTH_KEY", DEFAULT_API_AUTH_KEY)
    if not hmac.compare_digest(x_api_key or "", expected_key):
        client_ip = request.client.host if request and request.client else "unknown"
        logger.warning(
            "Unauthorized API access attempt: invalid or missing API key",
            extra={"client_ip": client_ip, "path": request.url.path},
        )
        raise HTTPException(status_code=401, detail="Invalid or missing API Key")


def _semantic_enabled_from_facade() -> bool:
    try:
        from api import main as api_main
    except ImportError:
        return bool(SEMANTIC_ENABLED)
    return bool(getattr(api_main, "SEMANTIC_ENABLED", SEMANTIC_ENABLED))


def _semantic_healthcheck_from_facade() -> dict:
    from api import main as api_main

    return api_main._semantic_service_healthcheck()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    _ = app
    key = os.getenv("API_AUTH_KEY", DEFAULT_API_AUTH_KEY)
    if key == DEFAULT_API_AUTH_KEY:
        logger.critical("SECURITY WARNING: You are using the default API Key. Please set API_AUTH_KEY in production.")
    initialize_database()
    if not is_db_ready():
        logger.warning("database_session_factory=unavailable")
    # Startup purge is lock-protected. If another service already purged, we skip.
    purge_result = run_startup_purge_if_enabled()
    logger.info("startup_purge_result=%s", purge_result)
    if _semantic_enabled_from_facade():
        try:
            # The API image only verifies the internal semantic service boundary.
            health = _semantic_healthcheck_from_facade()
            logger.info("semantic_backend_health=%s", health)
        except RuntimeError as exc:
            logger.critical("Semantic service misconfiguration: %s", exc)
            raise
    yield

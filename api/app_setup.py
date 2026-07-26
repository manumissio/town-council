import hmac
import logging
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from ipaddress import ip_address
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from pipeline.config import SEMANTIC_ENABLED
from pipeline.config_env import env_lower, env_raw
from pipeline.meilisearch_credentials import (
    DEVELOPMENT_MEILI_SEARCH_KEY,
    MEILI_SEARCH_KEY_FALLBACK_WARNING,
)
from pipeline.models import db_connect
from pipeline.startup_purge import run_startup_purge_if_enabled

DEFAULT_API_AUTH_KEY = "dev_secret_key_change_me"
DEVELOPMENT_APP_ENV = "dev"
UNSAFE_API_AUTH_KEY_MESSAGE = "API_AUTH_KEY must be set to a non-default, nonblank value when APP_ENV is not dev."
HEADER_UNSAFE_API_AUTH_KEY_MESSAGE = (
    "API_AUTH_KEY must contain printable ASCII characters without leading or trailing whitespace."
)
DATABASE_UNAVAILABLE_DETAIL = "Database service is unavailable"
API_KEY_HEADER = "x-api-key"
FORWARDED_CLIENT_HEADER = "x-forwarded-for"


def _api_key_matches(candidate: str | None) -> bool:
    expected_key = env_raw("API_AUTH_KEY", DEFAULT_API_AUTH_KEY)
    return hmac.compare_digest(candidate or "", expected_key)


def _forwarded_client_ip(request: Request) -> str | None:
    forwarded_client = request.headers.get(FORWARDED_CLIENT_HEADER)
    if (
        forwarded_client is None
        or forwarded_client != forwarded_client.strip()
        or "," in forwarded_client
    ):
        return None
    try:
        return str(ip_address(forwarded_client))
    except ValueError:
        return None


def rate_limit_client_key(request: Request) -> str:
    if _api_key_matches(request.headers.get(API_KEY_HEADER)):
        forwarded_client = _forwarded_client_ip(request)
        if forwarded_client is not None:
            return forwarded_client
    return get_remote_address(request)


# This protects the local API worker from expensive endpoint floods.
limiter = Limiter(key_func=rate_limit_client_key)

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
    if not _api_key_matches(x_api_key):
        client_ip = request.client.host if request and request.client else "unknown"
        logger.warning(
            "Unauthorized API access attempt: invalid or missing API key",
            extra={"client_ip": client_ip, "path": request.url.path},
        )
        raise HTTPException(status_code=401, detail="Invalid or missing API Key")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    _ = app
    api_auth_key = env_raw("API_AUTH_KEY", DEFAULT_API_AUTH_KEY)
    app_env = env_lower("APP_ENV", DEVELOPMENT_APP_ENV)
    normalized_api_auth_key = api_auth_key.strip()
    if app_env != DEVELOPMENT_APP_ENV and (
        normalized_api_auth_key == DEFAULT_API_AUTH_KEY or not normalized_api_auth_key
    ):
        raise RuntimeError(UNSAFE_API_AUTH_KEY_MESSAGE)
    if api_auth_key and (
        not api_auth_key.isascii()
        or not api_auth_key.isprintable()
        or api_auth_key != normalized_api_auth_key
    ):
        raise RuntimeError(HEADER_UNSAFE_API_AUTH_KEY_MESSAGE)
    if api_auth_key == DEFAULT_API_AUTH_KEY:
        logger.critical("SECURITY WARNING: You are using the default API Key. Please set API_AUTH_KEY in production.")
    from api.search import semantic_support, support_core

    if support_core.MEILI_MASTER_KEY == DEVELOPMENT_MEILI_SEARCH_KEY:
        logger.warning(MEILI_SEARCH_KEY_FALLBACK_WARNING)
    initialize_database()
    if not is_db_ready():
        logger.warning("database_session_factory=unavailable")
    # Startup purge is lock-protected. If another service already purged, we skip.
    purge_result = run_startup_purge_if_enabled()
    logger.info("startup_purge_result=%s", purge_result)
    if SEMANTIC_ENABLED:
        try:
            # The API image only verifies the internal semantic service boundary.
            health = semantic_support._semantic_service_healthcheck()
            logger.info("semantic_backend_health=%s", health)
        except RuntimeError as exc:
            logger.critical("Semantic service misconfiguration: %s", exc)
            raise
    yield

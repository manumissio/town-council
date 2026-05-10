from __future__ import annotations

import logging
import os
from typing import Final

from pipeline.metrics_provider_collector import RedisProviderMetricsCollector as _RedisProviderMetricsCollector


logger = logging.getLogger(__name__)
try:
    import redis  # type: ignore[import-untyped]
except ImportError:
    redis = None  # type: ignore[assignment]
    REDIS_OPERATION_ERRORS: Final[tuple[type[BaseException], ...]] = ()
else:
    REDIS_OPERATION_ERRORS = (redis.RedisError,)

REDIS_HOST_ENV: Final = "REDIS_HOST"
REDIS_PORT_ENV: Final = "REDIS_PORT"
REDIS_PASSWORD_ENV: Final = "REDIS_PASSWORD"
DEFAULT_REDIS_HOST: Final = "redis"
DEFAULT_REDIS_PORT: Final = "6379"
REDIS_DB: Final = 0
REDIS_WRITE_ERRORS: Final = REDIS_OPERATION_ERRORS + (OSError, RuntimeError, TimeoutError, TypeError, ValueError)

_REDIS_CLIENT = None
_REDIS_INIT = False
_REDIS_WARNED = False
_REDIS_BACKEND_UP = 0.0


def _redis_client() -> object | None:
    global _REDIS_BACKEND_UP, _REDIS_CLIENT, _REDIS_INIT, _REDIS_WARNED
    if _REDIS_INIT:
        return _REDIS_CLIENT
    _REDIS_INIT = True

    if redis is None:
        if not _REDIS_WARNED:
            logger.warning("metrics.redis_unavailable redis module unavailable; provider metrics backend degraded")
            _REDIS_WARNED = True
        _REDIS_BACKEND_UP = 0.0
        return None

    try:
        _REDIS_CLIENT = redis.Redis(
            host=os.getenv(REDIS_HOST_ENV, DEFAULT_REDIS_HOST),
            port=int(os.getenv(REDIS_PORT_ENV, DEFAULT_REDIS_PORT)),
            password=os.getenv(REDIS_PASSWORD_ENV, "") or None,
            db=REDIS_DB,
            decode_responses=True,
        )
        _REDIS_CLIENT.ping()
        _REDIS_BACKEND_UP = 1.0
        return _REDIS_CLIENT
    except REDIS_WRITE_ERRORS as error:
        if not _REDIS_WARNED:
            logger.warning(
                "metrics.redis_backend_unavailable falling back to local metrics only error=%s",
                error,
            )
            _REDIS_WARNED = True
        _REDIS_BACKEND_UP = 0.0
        _REDIS_CLIENT = None
        return None


def _redis_incr(key: str, amount: int = 1) -> None:
    global _REDIS_BACKEND_UP
    client = _redis_client()
    if client is None:
        return
    try:
        client.incrby(key, int(amount))
    except REDIS_WRITE_ERRORS:
        _REDIS_BACKEND_UP = 0.0


def _redis_hincrby(key: str, field: str, amount: int = 1) -> None:
    global _REDIS_BACKEND_UP
    client = _redis_client()
    if client is None:
        return
    try:
        client.hincrby(key, field, int(amount))
    except REDIS_WRITE_ERRORS:
        _REDIS_BACKEND_UP = 0.0


def _redis_hincrbyfloat(key: str, field: str, amount: float) -> None:
    global _REDIS_BACKEND_UP
    client = _redis_client()
    if client is None:
        return
    try:
        client.hincrbyfloat(key, field, float(amount))
    except REDIS_WRITE_ERRORS:
        _REDIS_BACKEND_UP = 0.0


def _get_redis_backend_up() -> float:
    return float(_REDIS_BACKEND_UP)


def _set_redis_backend_up(value: float) -> None:
    global _REDIS_BACKEND_UP
    _REDIS_BACKEND_UP = float(value)


class RedisProviderMetricsCollector(_RedisProviderMetricsCollector):
    def __init__(self) -> None:
        super().__init__(_redis_client, _get_redis_backend_up, _set_redis_backend_up, read_errors=REDIS_WRITE_ERRORS)

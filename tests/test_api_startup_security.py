import logging
from typing import Never

import h11
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from api import app_setup
from api.search import semantic_support, support_core
from pipeline.meilisearch_credentials import DEVELOPMENT_MEILI_SEARCH_KEY


DEFAULT_KEY_WARNING = "SECURITY WARNING: You are using the default API Key."
UNSAFE_KEY_MESSAGE = "API_AUTH_KEY must be set to a non-default, nonblank value when APP_ENV is not dev."
HEADER_UNSAFE_KEY_MESSAGE = (
    "API_AUTH_KEY must contain printable ASCII characters without leading or trailing whitespace."
)
CONFIGURED_API_KEY = "Configured Production Key_123"
CONFIGURED_MEILI_SEARCH_KEY = "Configured Search Key_123"
MEILI_FALLBACK_WARNING = "Meilisearch reader is using the development fallback key"
MASTER_KEY_SENTINEL = "master-key-must-not-appear-in-logs"


class _HealthySemanticResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, str]:
        return {"status": "ok"}


def _healthy_semantic_get(_url: str, *, timeout: float) -> _HealthySemanticResponse:
    _ = timeout
    return _HealthySemanticResponse()


def _fail_database_initialization() -> Never:
    raise AssertionError("database initialization must not run after unsafe key rejection")


def _protected_status() -> dict[str, str]:
    return {"status": "ok"}


@pytest.mark.parametrize(
    ("app_env", "api_auth_key", "expected_message"),
    [
        ("prod", app_setup.DEFAULT_API_AUTH_KEY, UNSAFE_KEY_MESSAGE),
        ("staging", app_setup.DEFAULT_API_AUTH_KEY, UNSAFE_KEY_MESSAGE),
        (" ", app_setup.DEFAULT_API_AUTH_KEY, UNSAFE_KEY_MESSAGE),
        ("prod", "", UNSAFE_KEY_MESSAGE),
        ("prod", "   ", UNSAFE_KEY_MESSAGE),
        ("prod", f" {app_setup.DEFAULT_API_AUTH_KEY} ", UNSAFE_KEY_MESSAGE),
        ("prod", " configured-production-key ", HEADER_UNSAFE_KEY_MESSAGE),
        ("prod", "configured-key-\x7f", HEADER_UNSAFE_KEY_MESSAGE),
        ("prod", "configured-key-\u00e9", HEADER_UNSAFE_KEY_MESSAGE),
        ("dev", "configured-key-\u00e9", HEADER_UNSAFE_KEY_MESSAGE),
    ],
)
def test_startup_rejects_unsafe_api_key(
    monkeypatch: pytest.MonkeyPatch,
    app_env: str,
    api_auth_key: str,
    expected_message: str,
) -> None:
    monkeypatch.setenv("APP_ENV", app_env)
    monkeypatch.setenv("API_AUTH_KEY", api_auth_key)
    monkeypatch.setattr(app_setup, "db_connect", _fail_database_initialization)
    app_setup.SessionLocal = None
    application = FastAPI(lifespan=app_setup.lifespan)

    with pytest.raises(RuntimeError, match=expected_message) as startup_error:
        with TestClient(application):
            pass

    if api_auth_key:
        assert api_auth_key not in str(startup_error.value)


@pytest.mark.parametrize("app_env", [None, " DeV "])
def test_dev_startup_allows_default_api_key_with_warning(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    app_env: str | None,
) -> None:
    if app_env is None:
        monkeypatch.delenv("APP_ENV", raising=False)
    else:
        monkeypatch.setenv("APP_ENV", app_env)
    monkeypatch.setenv("API_AUTH_KEY", app_setup.DEFAULT_API_AUTH_KEY)
    monkeypatch.setenv("STARTUP_PURGE_DERIVED", "false")
    monkeypatch.setattr(semantic_support.httpx, "get", _healthy_semantic_get)
    application = FastAPI(lifespan=app_setup.lifespan)

    with caplog.at_level(logging.CRITICAL, logger="town-council-api"):
        with TestClient(application):
            pass

    assert DEFAULT_KEY_WARNING in caplog.text
    assert app_setup.DEFAULT_API_AUTH_KEY not in caplog.text


def test_non_dev_startup_accepts_configured_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("API_AUTH_KEY", CONFIGURED_API_KEY)
    monkeypatch.setattr(support_core, "MEILI_SEARCH_KEY", CONFIGURED_MEILI_SEARCH_KEY)
    monkeypatch.setattr(support_core, "MEILI_MASTER_KEY", CONFIGURED_MEILI_SEARCH_KEY)
    monkeypatch.setenv("STARTUP_PURGE_DERIVED", "false")
    monkeypatch.setattr(semantic_support.httpx, "get", _healthy_semantic_get)
    application = FastAPI(lifespan=app_setup.lifespan)
    application.add_api_route(
        "/protected",
        _protected_status,
        dependencies=[Depends(app_setup.verify_api_key)],
    )

    with TestClient(application) as client:
        exact_key_response = client.get("/protected", headers={"X-API-Key": CONFIGURED_API_KEY})
        changed_key_response = client.get("/protected", headers={"X-API-Key": CONFIGURED_API_KEY.lower()})

    assert exact_key_response.status_code == 200
    assert changed_key_response.status_code == 401


def test_api_dev_startup_warns_with_development_search_key(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("API_AUTH_KEY", CONFIGURED_API_KEY)
    monkeypatch.setenv("MEILI_MASTER_KEY", MASTER_KEY_SENTINEL)
    monkeypatch.setattr(support_core, "MEILI_SEARCH_KEY", DEVELOPMENT_MEILI_SEARCH_KEY)
    monkeypatch.setattr(support_core, "MEILI_MASTER_KEY", DEVELOPMENT_MEILI_SEARCH_KEY)
    monkeypatch.setenv("STARTUP_PURGE_DERIVED", "false")
    monkeypatch.setattr(semantic_support.httpx, "get", _healthy_semantic_get)
    application = FastAPI(lifespan=app_setup.lifespan)

    with caplog.at_level(logging.WARNING, logger="town-council-api"):
        with TestClient(application):
            pass

    assert MEILI_FALLBACK_WARNING in caplog.text
    assert DEVELOPMENT_MEILI_SEARCH_KEY not in caplog.text
    assert MASTER_KEY_SENTINEL not in caplog.text


def test_h11_removes_edge_whitespace_but_preserves_internal_api_key_space() -> None:
    connection = h11.Connection(h11.SERVER)
    connection.receive_data(
        b"GET /protected HTTP/1.1\r\n"
        b"Host: test\r\n"
        b"X-API-Key:   Configured Production Key_123   \r\n"
        b"\r\n"
    )

    request = connection.next_event()

    assert isinstance(request, h11.Request)
    assert dict(request.headers)[b"x-api-key"] == CONFIGURED_API_KEY.encode()

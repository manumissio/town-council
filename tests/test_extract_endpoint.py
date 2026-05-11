import sys
import os
from unittest.mock import MagicMock
from kombu.exceptions import OperationalError

from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

# Add the project root to the path so we can import from api/main.py
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "api"))

# Mock heavy AI dependency before importing api.main
sys.modules["llama_cpp"] = MagicMock()

from api.main import app  # noqa: E402


client = TestClient(app)
VALID_KEY = "dev_secret_key_change_me"


def test_extract_requires_api_key():
    resp = client.post("/extract/1")
    assert resp.status_code in (401, 403)


def test_extract_404_when_catalog_missing(mocker):
    from api.main import get_db

    db = MagicMock()
    db.get.return_value = None

    def _mock_get_db():
        yield db

    app.dependency_overrides[get_db] = _mock_get_db
    try:
        resp = client.post("/extract/123", headers={"X-API-Key": VALID_KEY})
        assert resp.status_code == 404
    finally:
        del app.dependency_overrides[get_db]


def test_extract_rate_limit_still_enforced():
    from api.task_routes import build_task_router

    db = MagicMock()
    db.get.return_value = None

    def _mock_get_db():
        yield db

    async def _verify_api_key():
        return None

    rate_limiter = Limiter(key_func=get_remote_address)
    rate_limit_app = FastAPI()
    rate_limit_app.state.limiter = rate_limiter
    rate_limit_app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    rate_limit_app.include_router(
        build_task_router(
            limiter=rate_limiter,
            get_db_dependency=_mock_get_db,
            verify_api_key_dependency=_verify_api_key,
            task_facade=MagicMock(),
        )
    )

    rate_limit_client = TestClient(rate_limit_app, client=("extract-rate-limit-test", 50000))
    responses = [rate_limit_client.post("/extract/123") for _ in range(6)]
    assert [response.status_code for response in responses[:5]] == [404, 404, 404, 404, 404]
    assert responses[5].status_code == 429


def test_extract_cached_when_content_exists_and_not_forced(mocker):
    from api.main import get_db

    catalog = MagicMock(id=10, content="x" * 2000)
    db = MagicMock()
    db.get.return_value = catalog

    def _mock_get_db():
        yield db

    app.dependency_overrides[get_db] = _mock_get_db
    mocker.patch("api.main.extract_text_task.delay")
    try:
        resp = client.post("/extract/10", headers={"X-API-Key": VALID_KEY})
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["status"] == "cached"
        assert payload["catalog_id"] == 10
    finally:
        del app.dependency_overrides[get_db]


def test_extract_force_enqueues_task_even_when_cached(mocker):
    from api.main import get_db

    catalog = MagicMock(id=10, content="x" * 2000)
    db = MagicMock()
    db.get.return_value = catalog

    def _mock_get_db():
        yield db

    app.dependency_overrides[get_db] = _mock_get_db
    task = MagicMock()
    task.id = "task_extract_1"
    mocker.patch("api.main.extract_text_task.delay", return_value=task)
    try:
        resp = client.post("/extract/10?force=true&ocr_fallback=true", headers={"X-API-Key": VALID_KEY})
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["status"] == "processing"
        assert payload["task_id"] == "task_extract_1"
    finally:
        del app.dependency_overrides[get_db]


def test_extract_returns_503_when_enqueue_fails(mocker):
    from api.main import get_db

    catalog = MagicMock(id=10, content="")
    db = MagicMock()
    db.get.return_value = catalog

    def _mock_get_db():
        yield db

    app.dependency_overrides[get_db] = _mock_get_db
    mocker.patch("api.main.extract_text_task.delay", side_effect=OperationalError("broker down"))
    try:
        resp = client.post("/extract/10?force=true", headers={"X-API-Key": VALID_KEY})
        assert resp.status_code == 503
        assert resp.json()["detail"] == "Task queue unavailable"
    finally:
        del app.dependency_overrides[get_db]


def test_catalog_content_endpoint_returns_content(mocker):
    from api.main import get_db

    catalog = MagicMock(id=10, content="[PAGE 1]\nHello")
    db = MagicMock()
    db.get.return_value = catalog

    def _mock_get_db():
        yield db

    app.dependency_overrides[get_db] = _mock_get_db
    try:
        resp = client.get("/catalog/10/content", headers={"X-API-Key": VALID_KEY})
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["catalog_id"] == 10
        assert payload["chars"] > 0
        assert payload["has_page_markers"] is True
        assert "Hello" in payload["content"]
    finally:
        del app.dependency_overrides[get_db]

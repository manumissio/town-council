from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from semantic_service.main import app, get_db


def test_semantic_service_health_returns_backend_health_when_enabled(mocker):
    db = MagicMock()
    app.dependency_overrides[get_db] = lambda: db
    db.execute.return_value = 1
    mocker.patch("semantic_service.main.SEMANTIC_ENABLED", True)
    mocker.patch("semantic_service.main.get_semantic_backend").return_value.health.return_value = {
        "status": "ok",
        "engine": "faiss",
    }
    client = TestClient(app)
    try:
        resp = client.get("/health")
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["status"] == "healthy"
        assert payload["backend"]["engine"] == "faiss"
    finally:
        del app.dependency_overrides[get_db]

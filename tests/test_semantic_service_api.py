import os
from unittest.mock import MagicMock

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from fastapi.testclient import TestClient

from pipeline.semantic_index import SemanticCandidate, SemanticConfigError

from semantic_service.main import app, get_db


def test_semantic_service_health_returns_backend_health_when_enabled(mocker):
    db = MagicMock()
    app.dependency_overrides[get_db] = lambda: db
    db.execute.return_value = 1
    mocker.patch("semantic_service.main.SEMANTIC_ENABLED", True)
    mocker.patch("semantic_service.main.get_semantic_backend").return_value.health.return_value = {
        "status": "ok",
        "engine": "faiss",
        "detail": "/secret/path/index.faiss",
    }
    client = TestClient(app)
    try:
        resp = client.get("/health")
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["status"] == "healthy"
        assert payload["backend"]["engine"] == "faiss"
        assert "detail" not in payload["backend"]
    finally:
        del app.dependency_overrides[get_db]


def test_semantic_service_health_hides_backend_error_detail(mocker):
    db = MagicMock()
    app.dependency_overrides[get_db] = lambda: db
    db.execute.return_value = 1
    mocker.patch("semantic_service.main.SEMANTIC_ENABLED", True)
    mocker.patch("semantic_service.main.get_semantic_backend").return_value.health.return_value = {
        "status": "error",
        "error": "FileNotFoundError",
        "detail": "/secret/path/index.faiss",
    }
    client = TestClient(app)
    try:
        resp = client.get("/health")
        assert resp.status_code == 503
        response_text = resp.text
        assert resp.json()["detail"] == "Semantic backend unhealthy"
        assert "/secret/path" not in response_text
    finally:
        del app.dependency_overrides[get_db]


def test_semantic_service_health_does_not_echo_backend_health_engine(mocker):
    db = MagicMock()
    app.dependency_overrides[get_db] = lambda: db
    db.execute.return_value = 1
    mocker.patch("semantic_service.main.SEMANTIC_ENABLED", True)
    mocker.patch("semantic_service.main.SEMANTIC_BACKEND", "faiss")
    mocker.patch("semantic_service.main.get_semantic_backend").return_value.health.return_value = {
        "status": "ok",
        "engine": "secret-engine",
    }
    client = TestClient(app)
    try:
        resp = client.get("/health")
        assert resp.status_code == 200
        response_text = resp.text
        payload = resp.json()
        assert payload["backend"] == {"status": "ok", "engine": "faiss"}
        assert "secret-engine" not in response_text
    finally:
        del app.dependency_overrides[get_db]


def test_semantic_search_config_error_hides_exception_detail(mocker):
    db = MagicMock()
    app.dependency_overrides[get_db] = lambda: db
    mocker.patch("semantic_service.main.SEMANTIC_ENABLED", True)
    backend = MagicMock()
    backend.query.side_effect = SemanticConfigError("secret /path/model.bin")
    mocker.patch("semantic_service.main.get_semantic_backend", return_value=backend)
    client = TestClient(app)
    try:
        resp = client.get("/search/semantic?q=zoning")
        assert resp.status_code == 503
        response_text = resp.text
        assert "Semantic service is misconfigured" in response_text
        assert "secret" not in response_text
        assert "/path/model.bin" not in response_text
    finally:
        del app.dependency_overrides[get_db]


def test_semantic_search_hides_backend_health_detail_from_diagnostics(mocker):
    db = MagicMock()
    app.dependency_overrides[get_db] = lambda: db
    mocker.patch("semantic_service.main.SEMANTIC_ENABLED", True)
    backend = MagicMock()
    backend.query.return_value = [
        SemanticCandidate(
            row_id=1,
            score=0.9,
            metadata={"result_type": "meeting", "db_id": 10, "catalog_id": 101},
        )
    ]
    backend.health.return_value = {
        "status": "error",
        "error": "RuntimeError",
        "detail": "/secret/path/metadata.json",
    }
    mocker.patch("semantic_service.main.get_semantic_backend", return_value=backend)
    mocker.patch(
        "semantic_service.main._hydrate_meeting_hits",
        return_value=[{"id": "doc_10", "db_id": 10, "result_type": "meeting", "event_name": "Meeting"}],
    )
    mocker.patch("semantic_service.main._hydrate_agenda_hits", return_value=[])
    client = TestClient(app)
    try:
        resp = client.get("/search/semantic?q=zoning")
        assert resp.status_code == 200
        response_text = resp.text
        payload = resp.json()
        assert payload["semantic_diagnostics"]["engine"] is None
        assert "/secret/path" not in response_text
        assert "detail" not in response_text
    finally:
        del app.dependency_overrides[get_db]

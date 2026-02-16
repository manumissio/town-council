from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from api.main import app, get_db

VALID_KEY = "dev_secret_key_change_me"


def test_semantic_search_disabled_returns_503(mocker):
    db = MagicMock()
    app.dependency_overrides[get_db] = lambda: db
    mocker.patch("api.main.SEMANTIC_ENABLED", False)
    client = TestClient(app)
    try:
        resp = client.get("/search/semantic?q=zoning", headers={"X-API-Key": VALID_KEY})
        assert resp.status_code == 503
        assert "SEMANTIC_ENABLED" in resp.json()["detail"]
    finally:
        del app.dependency_overrides[get_db]

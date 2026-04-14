from unittest.mock import MagicMock

from fastapi import HTTPException
from fastapi.testclient import TestClient

import api.search_routes as search_routes
from api.main import app, get_db

VALID_KEY = "dev_secret_key_change_me"


def test_semantic_search_success_with_filters(mocker):
    mocker.patch("api.main.SEMANTIC_ENABLED", True)
    mocker.patch("api.main._semantic_service_healthcheck", return_value={"status": "healthy"})
    mocker.patch(
        "api.main._semantic_service_get_json",
        return_value={
            "hits": [{"id": "doc_10", "db_id": 10, "result_type": "meeting", "event_name": "Cupertino Meeting", "semantic_score": 0.9}],
            "estimatedTotalHits": 1,
            "limit": 20,
            "offset": 0,
            "semantic_diagnostics": {"engine": "faiss"},
        },
    )
    client = TestClient(app)
    resp = client.get("/search/semantic?q=zoning&city=cupertino", headers={"X-API-Key": VALID_KEY})
    assert resp.status_code == 200
    data = resp.json()
    assert data["estimatedTotalHits"] == 1
    assert data["hits"][0]["id"] == "doc_10"
    assert data["semantic_diagnostics"]["engine"] == "faiss"


def test_semantic_search_missing_artifacts_returns_503(mocker):
    mocker.patch("api.main.SEMANTIC_ENABLED", True)
    mocker.patch("api.main._semantic_service_healthcheck", return_value={"status": "healthy"})
    mocker.patch(
        "api.main._semantic_service_get_json",
        side_effect=HTTPException(
            status_code=503,
            detail="Semantic index artifacts are missing. Run `docker compose run --rm semantic python ../pipeline/reindex_semantic.py` and retry.",
        ),
    )
    client = TestClient(app)
    resp = client.get("/search/semantic?q=zoning", headers={"X-API-Key": VALID_KEY})
    assert resp.status_code == 503
    assert "reindex_semantic.py" in resp.json()["detail"]


def test_semantic_service_error_forwards_non_dict_json_detail(mocker):
    response = MagicMock()
    response.status_code = 502
    response.json.return_value = ["semantic", "error"]
    mocker.patch("api.search_routes.httpx.get", return_value=response)

    try:
        search_routes._semantic_service_get_json("/search/semantic", {"q": "zoning"})
    except HTTPException as exc:
        assert exc.status_code == 502
        assert exc.detail == ["semantic", "error"]
    else:
        raise AssertionError("Expected semantic service HTTPException")

import sys
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

# Mock heavy dependency before importing api.main
sys.modules["llama_cpp"] = MagicMock()

from api.main import app


client = TestClient(app)
VALID_KEY = "dev_secret_key_change_me"


def test_summarize_returns_cached_only_when_source_hash_matches(mocker):
    from api.main import get_db

    catalog = MagicMock(
        id=1,
        content="City council meeting discussed budget updates and adopted multiple motions after public comment.",
        summary="cached summary",
        content_hash="abc",
        summary_source_hash="abc",
    )

    db = MagicMock()
    db.get.return_value = catalog

    def _mock_get_db():
        yield db

    app.dependency_overrides[get_db] = _mock_get_db
    delay = mocker.patch("api.main.generate_summary_task.delay")
    try:
        resp = client.post("/summarize/1", headers={"X-API-Key": VALID_KEY})
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["status"] == "cached"
        delay.assert_not_called()
    finally:
        del app.dependency_overrides[get_db]


def test_summarize_returns_stale_when_hash_mismatches(mocker):
    from api.main import get_db

    catalog = MagicMock(
        id=1,
        content="City council meeting discussed budget updates and adopted multiple motions after public comment.",
        summary="old summary",
        content_hash="newhash",
        summary_source_hash="oldhash",
    )

    db = MagicMock()
    db.get.return_value = catalog

    def _mock_get_db():
        yield db

    app.dependency_overrides[get_db] = _mock_get_db
    delay = mocker.patch("api.main.generate_summary_task.delay")
    try:
        resp = client.post("/summarize/1", headers={"X-API-Key": VALID_KEY})
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["status"] == "stale"
        assert payload["summary"] == "old summary"
        delay.assert_not_called()
    finally:
        del app.dependency_overrides[get_db]

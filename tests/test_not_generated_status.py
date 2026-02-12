import os
import sys
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "api"))

sys.modules["llama_cpp"] = MagicMock()

from api.main import app, get_db  # noqa: E402


VALID_KEY = "dev_secret_key_change_me"
client = TestClient(app)


def test_derived_status_sets_not_generated_flags_for_empty_derivatives():
    catalog = MagicMock(
        id=77,
        content=(
            "Council discussed housing policy, budget amendments, transit planning, wildfire mitigation, "
            "stormwater upgrades, neighborhood traffic calming, permitting backlog reduction, and park maintenance."
        ),
        content_hash="h1",
        summary=None,
        summary_source_hash=None,
        topics=[],
        topics_source_hash=None,
    )
    db = MagicMock()
    db.get.return_value = catalog
    db.query.return_value.filter.return_value.count.return_value = 0

    def _mock_get_db():
        yield db

    app.dependency_overrides[get_db] = _mock_get_db
    try:
        response = client.get("/catalog/77/derived_status", headers={"X-API-Key": VALID_KEY})
        assert response.status_code == 200
        payload = response.json()
        assert payload["summary_not_generated_yet"] is True
        assert payload["topics_not_generated_yet"] is True
        assert payload["agenda_not_generated_yet"] is True
    finally:
        del app.dependency_overrides[get_db]

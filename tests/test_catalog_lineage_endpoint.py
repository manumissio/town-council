from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from api.main import app, get_db


def test_catalog_lineage_endpoint_returns_thread(mocker):
    mocker.patch("api.main.FEATURE_TRENDS_DASHBOARD", True)

    db = MagicMock()
    db.get.return_value = SimpleNamespace(id=101, lineage_id="lin-101", lineage_confidence=0.8)
    rows = [
        (
            SimpleNamespace(id=101, lineage_confidence=0.8),
            SimpleNamespace(),
            SimpleNamespace(name="Meeting A", record_date=SimpleNamespace(isoformat=lambda: "2025-01-10")),
            SimpleNamespace(display_name="Berkeley", name="Berkeley"),
        ),
        (
            SimpleNamespace(id=102, lineage_confidence=0.7),
            SimpleNamespace(),
            SimpleNamespace(name="Meeting B", record_date=SimpleNamespace(isoformat=lambda: "2025-02-10")),
            SimpleNamespace(display_name="Berkeley", name="Berkeley"),
        ),
    ]
    mocker.patch("api.main._lineage_rows", return_value=rows)

    def _get_db():
        yield db

    app.dependency_overrides[get_db] = _get_db
    client = TestClient(app)
    try:
        resp = client.get("/catalog/101/lineage")
        assert resp.status_code == 200
        data = resp.json()
        assert data["lineage_id"] == "lin-101"
        assert data["count"] == 2
        assert {m["catalog_id"] for m in data["meetings"]} == {101, 102}
    finally:
        del app.dependency_overrides[get_db]

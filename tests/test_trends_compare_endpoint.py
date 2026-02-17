from fastapi.testclient import TestClient

from api.main import app


def test_trends_compare_returns_bucketed_series(mocker):
    mocker.patch("api.main.FEATURE_TRENDS_DASHBOARD", True)
    mocker.patch(
        "api.main._collect_meeting_docs",
        side_effect=[
            [
                {"date": "2025-01-12", "topics": ["housing", "zoning"], "city": "ca_berkeley"},
                {"date": "2025-02-12", "topics": ["housing"], "city": "ca_berkeley"},
            ],
            [
                {"date": "2025-01-20", "topics": ["housing"], "city": "ca_cupertino"},
                {"date": "2025-02-03", "topics": ["zoning"], "city": "ca_cupertino"},
            ],
        ],
    )
    client = TestClient(app)

    resp = client.get(
        "/trends/compare?cities=berkeley&cities=cupertino&date_from=2025-01-01&date_to=2025-02-28&granularity=month&limit=2"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["granularity"] == "month"
    assert data["topics"] == ["housing", "zoning"]
    assert len(data["series"]) >= 2
    assert all("city" in row and "topics" in row for row in data["series"])

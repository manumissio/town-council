from fastapi.testclient import TestClient

from api.main import app


def test_trends_compare_returns_bucketed_series(mocker):
    mocker.patch("api.search.support_core.FEATURE_TRENDS_DASHBOARD", True)
    mock_index = mocker.Mock()

    def search_meetings(_query, search_params):
        if 'city = "ca_berkeley"' in search_params["filter"]:
            return {
                "hits": [
                    {"date": "2024-12-31", "topics": ["parks"], "city": "ca_berkeley"},
                    {"date": "2025-01-12", "topics": ["housing", "zoning"], "city": "ca_berkeley"},
                    {"date": "2025-02-12", "topics": ["housing"], "city": "ca_berkeley"},
                    {"date": "2025-03-01", "topics": ["water"], "city": "ca_berkeley"},
                ]
            }
        return {
            "hits": [
                {"date": "2024-12-20", "topics": ["parks"], "city": "ca_cupertino"},
                {"date": "2025-01-20", "topics": ["housing"], "city": "ca_cupertino"},
                {"date": "2025-02-03", "topics": ["zoning"], "city": "ca_cupertino"},
                {"date": "2025-03-05", "topics": ["water"], "city": "ca_cupertino"},
            ]
        }

    mock_index.search.side_effect = search_meetings
    mocker.patch("api.search.support_core.client.index", return_value=mock_index)
    client = TestClient(app)

    resp = client.get(
        "/trends/compare?cities=berkeley&cities=cupertino&date_from=2025-01-01&date_to=2025-02-28&granularity=month&limit=2"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["granularity"] == "month"
    assert data["topics"] == ["housing", "zoning"]
    assert data["series"] == [
        {"city": "ca_berkeley", "bucket": "2025-01-01", "topics": {"housing": 1, "zoning": 1}},
        {"city": "ca_berkeley", "bucket": "2025-02-01", "topics": {"housing": 1, "zoning": 0}},
        {"city": "ca_cupertino", "bucket": "2025-01-01", "topics": {"housing": 1, "zoning": 0}},
        {"city": "ca_cupertino", "bucket": "2025-02-01", "topics": {"housing": 0, "zoning": 1}},
    ]
    search_params = [search_call.args[1] for search_call in mock_index.search.call_args_list]
    assert {tuple(params["filter"]) for params in search_params} == {
        ('result_type = "meeting"', 'city = "ca_berkeley"'),
        ('result_type = "meeting"', 'city = "ca_cupertino"'),
    }
    assert all(params["limit"] == 200 and params["offset"] == 0 for params in search_params)
    assert all(params["attributesToRetrieve"] == ["topics", "date", "city"] for params in search_params)

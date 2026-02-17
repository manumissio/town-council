from fastapi.testclient import TestClient

from api.main import app


def test_trends_topics_returns_facet_distribution(mocker):
    mocker.patch("api.main.FEATURE_TRENDS_DASHBOARD", True)
    mock_index = mocker.Mock()
    mock_index.search.return_value = {
        "facetDistribution": {
            "topics": {
                "housing": 9,
                "budget": 6,
            }
        }
    }
    mocker.patch("api.main.client.index", return_value=mock_index)
    client = TestClient(app)
    resp = client.get("/trends/topics?city=berkeley&limit=1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["city"] == "ca_berkeley"
    assert data["items"] == [{"topic": "housing", "count": 9}]


def test_trends_topics_feature_flag_disabled(mocker):
    mocker.patch("api.main.FEATURE_TRENDS_DASHBOARD", False)
    client = TestClient(app)
    resp = client.get("/trends/topics")
    assert resp.status_code == 503

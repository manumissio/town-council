from fastapi.testclient import TestClient

from api.main import app


def test_trends_export_csv(mocker):
    mocker.patch("api.main.FEATURE_TRENDS_DASHBOARD", True)
    mock_index = mocker.Mock()
    mock_index.search.return_value = {
        "facetDistribution": {"topics": {"housing": 4, "budget": 2}}
    }
    mocker.patch("api.main.client.index", return_value=mock_index)
    client = TestClient(app)

    resp = client.get("/trends/export?format=csv&city=berkeley")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    body = resp.text
    assert "topic,count,city,date_from,date_to" in body
    assert "housing,4,ca_berkeley" in body

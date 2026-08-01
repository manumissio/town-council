import pytest
from pytest_mock import MockerFixture
from fastapi.testclient import TestClient
from fastapi import HTTPException
from datetime import UTC, datetime
from itertools import count
import sys
import os
from time import monotonic
from unittest.mock import MagicMock
from kombu.exceptions import OperationalError
from meilisearch.errors import MeilisearchCommunicationError, MeilisearchError, MeilisearchTimeoutError
from meilisearch.models.index import IndexStats

# Add the project root to the path so we can import from api/main.py
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'api'))

# Mock heavy AI dependency before importing api.main
sys.modules["llama_cpp"] = MagicMock()

from api.main import app
from pipeline.agenda_resolver import agenda_items_look_low_quality

client = TestClient(app)
VALID_KEY = "dev_secret_key_change_me"
BERKELEY_METADATA_FACETS = {
    "facetDistribution": {
        "city": {"ca_dublin": 5, "ca_berkeley": 10},
        "organization": {"Planning Commission": 5, "City Council": 10},
        "meeting_category": {"Special": 5, "Regular": 10},
    }
}
DUBLIN_METADATA_FACETS = {
    "facetDistribution": {
        "city": {"ca_dublin": 5},
        "organization": {"Planning Commission": 5},
        "meeting_category": {"Special": 5},
    }
}
EMPTY_METADATA = {"cities": [], "organizations": [], "meeting_types": []}
METADATA_TEST_EPOCHS = count(start=monotonic() + 10_000.0, step=10_000.0)


@pytest.fixture
def metadata_cache_runtime(
    mocker: MockerFixture,
) -> tuple[list[float], MagicMock]:
    metadata_time = [next(METADATA_TEST_EPOCHS)]
    mocker.patch("api.search_read_routes.monotonic", side_effect=lambda: metadata_time[0])
    metadata_index = mocker.Mock()
    metadata_index.search.return_value = BERKELEY_METADATA_FACETS
    mocker.patch("api.search.support_core.client.index", return_value=metadata_index)
    return metadata_time, metadata_index


def test_read_root():
    """Test the root endpoint of the API."""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "message": "Town Council API is running. Go to /docs for the Swagger UI."}


def test_app_uses_lifespan_startup():
    from api.main import app as api_app

    assert api_app.router.lifespan_context is not None


def test_cors_preflight_omits_credentials_for_allowed_origin():
    response = client.options(
        "/stats",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "access-control-allow-credentials" not in response.headers


def test_cors_preflight_rejects_disallowed_origin():
    response = client.options(
        "/stats",
        headers={
            "Origin": "https://attacker.example",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers
    assert "access-control-allow-credentials" not in response.headers


def test_stats_response_is_minimized(mocker):
    search_index = mocker.Mock()
    search_index.get_stats.return_value = IndexStats(
        {
            "numberOfDocuments": 42,
            "isIndexing": True,
            "fieldDistribution": {"content": 42},
        }
    )
    mocker.patch("api.search.support_core.client.index", return_value=search_index)

    response = client.get("/stats")

    assert response.status_code == 200
    assert response.json() == {"number_of_documents": 42}


def test_stats_failure_returns_503(mocker):
    search_index = mocker.Mock()
    search_index.get_stats.side_effect = RuntimeError("search unavailable")
    mocker.patch("api.search.support_core.client.index", return_value=search_index)

    response = client.get("/stats")

    assert response.status_code == 503
    assert response.json() == {"detail": "Search engine unreachable"}


@pytest.mark.parametrize(
    ("elapsed_seconds", "expected_cities"),
    [(3599.0, ["Berkeley", "Dublin"]), (3600.0, ["Dublin"])],
    ids=["before-expiry", "at-expiry"],
)
def test_metadata_endpoint_uses_snapshot_until_expiry(
    metadata_cache_runtime: tuple[list[float], MagicMock],
    elapsed_seconds: float,
    expected_cities: list[str],
) -> None:
    metadata_time, metadata_index = metadata_cache_runtime
    first_request_time = metadata_time[0]
    first_response = client.get("/metadata", headers={"X-API-Key": VALID_KEY})
    metadata_index.search.return_value = DUBLIN_METADATA_FACETS
    metadata_time[0] = first_request_time + elapsed_seconds
    second_response = client.get("/metadata", headers={"X-API-Key": VALID_KEY})

    assert first_response.status_code == 200
    assert first_response.json() == {
        "cities": ["Berkeley", "Dublin"],
        "organizations": ["City Council", "Planning Commission"],
        "meeting_types": ["Regular", "Special"],
    }
    assert second_response.status_code == 200
    assert second_response.json()["cities"] == expected_cities


def test_metadata_endpoint_caches_failure_payload_until_expiry(
    metadata_cache_runtime: tuple[list[float], MagicMock],
) -> None:
    metadata_time, metadata_index = metadata_cache_runtime
    metadata_index.search.side_effect = MeilisearchCommunicationError("unavailable")
    failed_response = client.get("/metadata", headers={"X-API-Key": VALID_KEY})
    metadata_index.search.side_effect = None
    metadata_time[0] += 3599.0
    cached_response = client.get("/metadata", headers={"X-API-Key": VALID_KEY})

    assert failed_response.status_code == 200
    assert failed_response.json() == EMPTY_METADATA
    assert cached_response.json() == EMPTY_METADATA


def test_search_endpoint_params(mocker):
    """Test the /search endpoint handles query parameters correctly and builds filters."""
    mock_index = mocker.Mock()
    mock_index.search.return_value = {"hits": [], "estimatedTotalHits": 0}
    mocker.patch("api.search.support_core.client.index", return_value=mock_index)
    
    # Test with multiple filters (meeting-only by default)
    response = client.get("/search?q=zoning&city=berkeley&meeting_type=Regular&limit=10&offset=5", headers={"X-API-Key": VALID_KEY})
    assert response.status_code == 200
    
    # Verify the parameters passed to Meilisearch search()
    mock_index.search.assert_called_once()
    args, _ = mock_index.search.call_args
    assert args[0] == "zoning"
    
    search_params = args[1]
    # Check if filters are correctly built
    # UI labels (e.g. "Berkeley") are normalized to the indexed facet key (e.g. "ca_berkeley").
    assert 'city = "ca_berkeley"' in search_params['filter']
    assert 'meeting_category = "Regular"' in search_params['filter']
    assert 'result_type = "meeting"' in search_params['filter']
    assert "sort" not in search_params


def test_search_semantic_flag_delegates_to_semantic_service(mocker):
    mocker.patch("api.search.support_core.SEMANTIC_ENABLED", True)
    semantic_response = MagicMock(status_code=200)
    semantic_response.json.return_value = {
        "hits": [],
        "estimatedTotalHits": 0,
        "semantic_diagnostics": {"engine": "faiss"},
    }
    semantic_get = mocker.patch(
        "api.search.semantic_support.httpx.get",
        return_value=semantic_response,
    )

    response = client.get(
        "/search?q=zoning&semantic=true&city=berkeley&meeting_type=Regular&limit=10&offset=5",
        headers={"X-API-Key": VALID_KEY},
    )
    assert response.status_code == 200
    assert response.json()["semantic_diagnostics"]["engine"] == "faiss"
    semantic_params = semantic_get.call_args.kwargs["params"]
    assert semantic_params == {
        "q": "zoning",
        "city": "berkeley",
        "include_agenda_items": False,
        "meeting_type": "Regular",
        "org": None,
        "date_from": None,
        "date_to": None,
        "limit": 10,
        "offset": 5,
    }


def test_search_endpoint_normalizes_meeting_type_and_org_whitespace(mocker):
    mock_index = mocker.Mock()
    mock_index.search.return_value = {"hits": [], "estimatedTotalHits": 0}
    mocker.patch("api.search.support_core.client.index", return_value=mock_index)

    response = client.get(
        "/search?q=zoning&meeting_type=%20%20Regular%20%20Meeting%20&org=%20City%20%20Council%20",
        headers={"X-API-Key": VALID_KEY},
    )
    assert response.status_code == 200

    search_params = mock_index.search.call_args[0][1]
    assert 'meeting_category = "Regular Meeting"' in search_params["filter"]
    assert 'organization = "City Council"' in search_params["filter"]


def test_search_rejects_invalid_city_filter(mocker):
    mock_index = mocker.Mock()
    mocker.patch("api.search.support_core.client.index", return_value=mock_index)

    response = client.get("/search?q=zoning&city=%21%21%21", headers={"X-API-Key": VALID_KEY})
    assert response.status_code == 400
    assert "City filter" in response.json()["detail"]


def test_search_sort_newest_sets_meilisearch_sort(mocker):
    mock_index = mocker.Mock()
    mock_index.search.return_value = {"hits": [], "estimatedTotalHits": 0}
    mocker.patch("api.search.support_core.client.index", return_value=mock_index)

    response = client.get("/search?q=zoning&sort=newest", headers={"X-API-Key": VALID_KEY})
    assert response.status_code == 200
    search_params = mock_index.search.call_args[0][1]
    assert search_params["sort"] == ["date:desc"]


def test_search_sort_oldest_sets_meilisearch_sort(mocker):
    mock_index = mocker.Mock()
    mock_index.search.return_value = {"hits": [], "estimatedTotalHits": 0}
    mocker.patch("api.search.support_core.client.index", return_value=mock_index)

    response = client.get("/search?q=zoning&sort=oldest", headers={"X-API-Key": VALID_KEY})
    assert response.status_code == 200
    search_params = mock_index.search.call_args[0][1]
    assert search_params["sort"] == ["date:asc"]


def test_search_sort_relevance_does_not_set_meilisearch_sort(mocker):
    mock_index = mocker.Mock()
    mock_index.search.return_value = {"hits": [], "estimatedTotalHits": 0}
    mocker.patch("api.search.support_core.client.index", return_value=mock_index)

    response = client.get("/search?q=zoning&sort=relevance", headers={"X-API-Key": VALID_KEY})
    assert response.status_code == 200
    search_params = mock_index.search.call_args[0][1]
    assert "sort" not in search_params


def test_search_sort_invalid_returns_400(mocker):
    mock_index = mocker.Mock()
    mock_index.search.return_value = {"hits": [], "estimatedTotalHits": 0}
    mocker.patch("api.search.support_core.client.index", return_value=mock_index)

    response = client.get("/search?q=zoning&sort=wat", headers={"X-API-Key": VALID_KEY})
    assert response.status_code == 400


def test_search_sort_rejected_by_meilisearch_returns_actionable_400(mocker):
    mock_index = mocker.Mock()
    mock_index.search.side_effect = MeilisearchError("Attribute `date` is not sortable. Invalid sort.")
    mocker.patch("api.search.support_core.client.index", return_value=mock_index)

    response = client.get("/search?q=zoning&sort=newest", headers={"X-API-Key": VALID_KEY})
    assert response.status_code == 400
    assert "reindex_only.py" in response.json()["detail"]


def test_search_truncates_people_metadata_in_hits_and_formatted_hits(mocker):
    people_metadata = [{"name": f"Person {idx}"} for idx in range(12)]
    mock_index = mocker.Mock()
    mock_index.search.return_value = {
        "hits": [
            {
                "people_metadata": list(people_metadata),
                "_formatted": {"people_metadata": list(people_metadata)},
            }
        ],
        "estimatedTotalHits": 1,
    }
    mocker.patch("api.search.support_core.client.index", return_value=mock_index)

    response = client.get("/search?q=zoning", headers={"X-API-Key": VALID_KEY})

    assert response.status_code == 200
    hit = response.json()["hits"][0]
    assert len(hit["people_metadata"]) == 10
    assert len(hit["_formatted"]["people_metadata"]) == 10


def test_search_timeout_returns_503(mocker):
    mock_index = mocker.Mock()
    mock_index.search.side_effect = MeilisearchTimeoutError("timeout")
    mocker.patch("api.search.support_core.client.index", return_value=mock_index)

    response = client.get("/search?q=zoning", headers={"X-API-Key": VALID_KEY})

    assert response.status_code == 503
    assert response.json()["detail"] == "Search engine timed out"


def test_search_unavailable_returns_503(mocker):
    mock_index = mocker.Mock()
    mock_index.search.side_effect = MeilisearchCommunicationError("unavailable")
    mocker.patch("api.search.support_core.client.index", return_value=mock_index)

    response = client.get("/search?q=zoning", headers={"X-API-Key": VALID_KEY})

    assert response.status_code == 503
    assert response.json()["detail"] == "Search engine unavailable"


def test_search_generic_meilisearch_error_returns_500(mocker):
    mock_index = mocker.Mock()
    mock_index.search.side_effect = MeilisearchError("unexpected")
    mocker.patch("api.search.support_core.client.index", return_value=mock_index)

    response = client.get("/search?q=zoning", headers={"X-API-Key": VALID_KEY})

    assert response.status_code == 500
    assert response.json()["detail"] == "Internal search engine error"

def test_search_injection_protection(mocker):
    """
    Test: Does the search endpoint reject malicious city filter strings?
    (Fixes Audit Issue #2)
    """
    mock_index = mocker.Mock()
    mock_index.search.return_value = {"hits": []}
    mocker.patch("api.search.support_core.client.index", return_value=mock_index)
    
    # Attempt a "Quote Escape" attack in the city parameter
    malicious_city = 'berkeley" OR 1=1 OR city="'
    response = client.get(f"/search?q=test&city={malicious_city}", headers={"X-API-Key": VALID_KEY})
    assert response.status_code == 400
    assert "unsupported characters" in response.json()["detail"].lower()
    mock_index.search.assert_not_called()

def test_api_database_unavailable(mocker):
    """
    Test: Does the API return 503 if the database fails to load?
    """
    from api.main import get_db
    
    # 1. Simulate a failed DB initialization via dependency override
    def mock_get_db_fail():
        raise HTTPException(status_code=503, detail="Database service is unavailable")
    
    app.dependency_overrides[get_db] = mock_get_db_fail
    
    try:
        # 2. Action: Try to hit a DB-dependent endpoint
        response = client.get("/people", headers={"X-API-Key": VALID_KEY})
        
        # 3. Verify
        assert response.status_code == 503
        assert "Database service is unavailable" in response.json()["detail"]
    finally:
        # Cleanup: Remove the override so other tests pass
        del app.dependency_overrides[get_db]


def test_get_db_returns_sanitized_503_when_database_init_fails(mocker):
    from api import app_setup

    mocker.patch.object(
        app_setup,
        "db_connect",
        side_effect=RuntimeError("DATABASE_URL is not set"),
    )
    app_setup.SessionLocal = None
    app_setup._db_init_error = None

    try:
        with pytest.raises(HTTPException) as excinfo:
            next(app_setup.get_db())
        assert excinfo.value.status_code == 503
        assert excinfo.value.detail == "Database service is unavailable"
    finally:
        app_setup.SessionLocal = None
        app_setup._db_init_error = None


def test_initialize_database_recovers_after_transient_failure(mocker):
    from api import app_setup

    class _ClosableSession:
        closed = False

        def close(self) -> None:
            self.closed = True

    fake_session = _ClosableSession()
    fake_engine = MagicMock()
    mocker.patch.object(
        app_setup,
        "db_connect",
        side_effect=[RuntimeError("first failure"), fake_engine],
    )
    mocker.patch.object(
        app_setup,
        "sessionmaker",
        return_value=lambda: fake_session,
    )
    app_setup.SessionLocal = None
    app_setup._db_init_error = None

    try:
        with pytest.raises(HTTPException) as excinfo:
            next(app_setup.get_db())
        assert excinfo.value.status_code == 503

        session_dependency = app_setup.get_db()
        assert next(session_dependency) is fake_session
        with pytest.raises(StopIteration):
            next(session_dependency)
        assert fake_session.closed is True
    finally:
        app_setup.SessionLocal = None
        app_setup._db_init_error = None


def test_task_status_rejects_invalid_uuid():
    response = client.get("/tasks/not-a-uuid")
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid task_id format"


@pytest.mark.parametrize("route", ["/summarize/1", "/segment/1", "/votes/1", "/topics/1", "/extract/1"])
def test_task_mutation_routes_require_api_key(route):
    response = client.post(route)

    assert response.status_code == 401


def test_lineage_endpoint_not_gated_by_trends_flag():
    from api.main import get_db

    rows = [
        (
            MagicMock(id=101, lineage_id="lin-101", lineage_confidence=0.8, lineage_updated_at=None, summary="Summary"),
            MagicMock(),
            MagicMock(name="Meeting A", record_date=MagicMock(isoformat=lambda: "2025-01-10")),
            MagicMock(display_name="ca_berkeley", name="Berkeley"),
        )
    ]
    db = MagicMock()
    lineage_query = db.query.return_value.join.return_value.join.return_value.join.return_value
    lineage_query.filter.return_value.order_by.return_value.all.return_value = rows

    def _get_db():
        yield db

    app.dependency_overrides[get_db] = _get_db
    try:
        response = client.get("/lineage/lin-101", headers={"X-API-Key": VALID_KEY})
        assert response.status_code == 200
        assert response.json()["lineage_id"] == "lin-101"
        assert response.json()["meetings"][0]["lineage_updated_at"] is None
    finally:
        del app.dependency_overrides[get_db]


def test_lineage_endpoint_emits_offset_bearing_timestamp():
    from api.main import get_db

    rows = [
        (
            MagicMock(
                id=101,
                lineage_id="lin-101",
                lineage_confidence=0.8,
                lineage_updated_at=datetime(2026, 7, 25, 12, 30, tzinfo=UTC),
                summary="Summary",
            ),
            MagicMock(),
            MagicMock(name="Meeting A", record_date=MagicMock(isoformat=lambda: "2026-07-25")),
            MagicMock(display_name="ca_berkeley", name="Berkeley"),
        )
    ]
    db = MagicMock()
    lineage_query = db.query.return_value.join.return_value.join.return_value.join.return_value
    lineage_query.filter.return_value.order_by.return_value.all.return_value = rows

    def _get_db():
        yield db

    app.dependency_overrides[get_db] = _get_db
    try:
        response = client.get("/lineage/lin-101", headers={"X-API-Key": VALID_KEY})
        meeting = response.json()["meetings"][0]

        assert response.status_code == 200
        assert "lineage_updated_at" in meeting
        assert meeting["lineage_updated_at"] == "2026-07-25T12:30:00+00:00"
    finally:
        del app.dependency_overrides[get_db]


def test_agenda_quality_gate_flags_low_quality_cache():
    """Low-quality cached agenda items should be considered stale."""
    bad_items = [
        MagicMock(title="", page_number=1),
        MagicMock(title="Special Closed Meeting 10/03/11", page_number=1),
        MagicMock(title="I hereby request that the City Clerk provide notice to each member.", page_number=1),
        MagicMock(title="state of emergency continues to directly impact the ability of the members to meet safely in person and", page_number=1),
    ]
    assert agenda_items_look_low_quality(bad_items) is True


def test_segment_force_bypasses_cache(mocker):
    """
    If cached agenda items exist, `force=true` should still enqueue regeneration.
    """
    from api.main import get_db
    catalog = MagicMock(id=401, content="City council meeting discussed budget updates and adopted multiple motions after public comment.")

    db = MagicMock()
    db.get.return_value = catalog
    query = db.query.return_value
    query.filter_by.return_value.order_by.return_value.all.return_value = [
        MagicMock(title="Budget Amendment", order=1)
    ]

    def _mock_get_db():
        yield db

    app.dependency_overrides[get_db] = _mock_get_db
    mock_task = MagicMock()
    mock_task.id = "task123"
    send_task = mocker.patch("api.task_dispatch.celery_app.send_task", return_value=mock_task)

    try:
        resp = client.post("/segment/401?force=true", headers={"X-API-Key": VALID_KEY})
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["status"] == "processing"
        assert payload["task_id"] == "task123"
        send_task.assert_called_once_with(
            "pipeline.tasks.segment_agenda_task",
            args=(401,),
            kwargs={},
        )
    finally:
        del app.dependency_overrides[get_db]


def test_segment_returns_cached_when_not_forced_and_quality_ok(mocker):
    """
    Default behavior: if cache exists and doesn't look low quality, return cached items.
    """
    from api.main import get_db

    catalog = MagicMock(id=401, content="City council meeting discussed budget updates and adopted multiple motions after public comment.")
    existing = [MagicMock(title="Budget Amendment", order=1)]

    db = MagicMock()
    db.get.return_value = catalog
    query = db.query.return_value
    query.filter_by.return_value.order_by.return_value.all.return_value = existing

    def _mock_get_db():
        yield db

    app.dependency_overrides[get_db] = _mock_get_db
    send_task = mocker.patch("api.task_dispatch.celery_app.send_task")

    try:
        resp = client.post("/segment/401", headers={"X-API-Key": VALID_KEY})
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["status"] == "cached"
        send_task.assert_not_called()
    finally:
        del app.dependency_overrides[get_db]


def test_votes_endpoint_enqueues_async_task(mocker):
    from api.main import get_db

    catalog = MagicMock(id=777, content="Meeting text")
    db = MagicMock()
    db.get.return_value = catalog

    def _mock_get_db():
        yield db

    app.dependency_overrides[get_db] = _mock_get_db
    fake_task = MagicMock()
    fake_task.id = "task-votes-777"
    send_task = mocker.patch("api.task_dispatch.celery_app.send_task", return_value=fake_task)
    try:
        resp = client.post("/votes/777", headers={"X-API-Key": VALID_KEY})
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["status"] == "processing"
        assert payload["task_id"] == "task-votes-777"
        send_task.assert_called_once_with(
            "pipeline.tasks.extract_votes_task",
            args=(777,),
            kwargs={"force": False},
        )
    finally:
        del app.dependency_overrides[get_db]


def test_votes_endpoint_returns_503_when_enqueue_fails(mocker):
    from api.main import get_db

    catalog = MagicMock(id=777, content="Meeting text")
    db = MagicMock()
    db.get.return_value = catalog

    def _mock_get_db():
        yield db

    app.dependency_overrides[get_db] = _mock_get_db
    mocker.patch("api.task_dispatch.celery_app.send_task", side_effect=OperationalError("broker down"))
    try:
        resp = client.post("/votes/777", headers={"X-API-Key": VALID_KEY})
        assert resp.status_code == 503
        assert resp.json()["detail"] == "Task queue unavailable"
    finally:
        del app.dependency_overrides[get_db]


def test_summarize_force_bypasses_cache(mocker):
    """
    If a cached summary exists, `force=true` should still enqueue regeneration.
    """
    from api.main import get_db

    catalog = MagicMock(
        id=401,
        content="City council meeting discussed budget updates and adopted multiple motions after public comment.",
        summary="cached summary",
    )

    db = MagicMock()
    db.get.return_value = catalog

    def _mock_get_db():
        yield db

    app.dependency_overrides[get_db] = _mock_get_db
    mock_task = MagicMock()
    mock_task.id = "task_summary_1"
    send_task = mocker.patch("api.task_dispatch.celery_app.send_task", return_value=mock_task)

    try:
        resp = client.post("/summarize/401?force=true", headers={"X-API-Key": VALID_KEY})
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["status"] == "processing"
        assert payload["task_id"] == "task_summary_1"
        send_task.assert_called_once_with(
            "pipeline.tasks.generate_summary_task",
            args=(401,),
            kwargs={"force": True},
        )
    finally:
        del app.dependency_overrides[get_db]


def test_summarize_returns_blocked_low_signal_without_queueing(mocker):
    from api.main import get_db

    catalog = MagicMock(id=909, content="Agenda", summary=None, content_hash="h1", summary_source_hash=None)
    db = MagicMock()
    db.get.return_value = catalog

    def _mock_get_db():
        yield db

    app.dependency_overrides[get_db] = _mock_get_db
    send_task = mocker.patch("api.task_dispatch.celery_app.send_task")
    try:
        resp = client.post("/summarize/909", headers={"X-API-Key": VALID_KEY})
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["status"] == "blocked_low_signal"
        assert "Not enough extracted text" in payload["reason"]
        send_task.assert_not_called()
    finally:
        del app.dependency_overrides[get_db]


def test_summarize_empty_agenda_bypasses_low_signal_gate(mocker):
    from api.main import get_db

    catalog = MagicMock(
        id=910,
        content="Agenda",
        summary=None,
        content_hash="h1",
        summary_source_hash=None,
        agenda_segmentation_status="empty",
    )
    db = MagicMock()
    db.get.return_value = catalog
    from pipeline.models import AgendaItem, Document

    def _query_side_effect(model):
        query = MagicMock()
        if model is Document:
            query.filter_by.return_value.first.return_value = MagicMock(category="agenda")
        elif model is AgendaItem:
            query.filter_by.return_value.order_by.return_value.all.return_value = []
        return query

    db.query.side_effect = _query_side_effect

    def _mock_get_db():
        yield db

    app.dependency_overrides[get_db] = _mock_get_db
    mock_task = MagicMock()
    mock_task.id = "task_summary_empty_agenda"
    send_task = mocker.patch("api.task_dispatch.celery_app.send_task", return_value=mock_task)
    try:
        resp = client.post("/summarize/910", headers={"X-API-Key": VALID_KEY})
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["status"] == "processing"
        assert payload["task_id"] == "task_summary_empty_agenda"
        send_task.assert_called_once_with(
            "pipeline.tasks.generate_summary_task",
            args=(910,),
            kwargs={"force": False},
        )
    finally:
        del app.dependency_overrides[get_db]


def test_topics_returns_blocked_low_signal_without_queueing(mocker):
    from api.main import get_db

    catalog = MagicMock(id=909, content="Agenda", topics=["Old"], content_hash="h1", topics_source_hash="h1")
    db = MagicMock()
    db.get.return_value = catalog

    def _mock_get_db():
        yield db

    app.dependency_overrides[get_db] = _mock_get_db
    send_task = mocker.patch("api.task_dispatch.celery_app.send_task")
    try:
        resp = client.post("/topics/909", headers={"X-API-Key": VALID_KEY})
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["status"] == "blocked_low_signal"
        assert "Not enough extracted text" in payload["reason"]
        assert payload["topics"] == []
        send_task.assert_not_called()
    finally:
        del app.dependency_overrides[get_db]


def test_topics_endpoint_enqueues_async_task(mocker):
    from api.main import get_db

    catalog = MagicMock(
        id=911,
        content=(
            "City council meeting discussed budget updates, transportation allocations, housing projects, "
            "public safety staffing, and adopted multiple motions after extended public comment."
        ),
        topics=None,
        content_hash="topics-hash",
        topics_source_hash=None,
    )
    db = MagicMock()
    db.get.return_value = catalog

    def _mock_get_db():
        yield db

    app.dependency_overrides[get_db] = _mock_get_db
    task = MagicMock(id="task-topics-911")
    send_task = mocker.patch("api.task_dispatch.celery_app.send_task", return_value=task)
    try:
        response = client.post("/topics/911?force=true", headers={"X-API-Key": VALID_KEY})

        assert response.status_code == 200
        assert response.json() == {
            "status": "processing",
            "task_id": "task-topics-911",
            "poll_url": "/tasks/task-topics-911",
        }
        send_task.assert_called_once_with(
            "enrichment.generate_topics",
            args=(911,),
            kwargs={"force": True},
        )
    finally:
        del app.dependency_overrides[get_db]


def test_derived_status_exposes_blocked_reasons_for_low_signal_content():
    from api.main import get_db

    catalog = MagicMock(
        id=909,
        content="Agenda",
        content_hash="h1",
        summary="old summary",
        summary_source_hash="h1",
        topics=["Old"],
        topics_source_hash="h1",
    )
    db = MagicMock()
    db.get.return_value = catalog
    db.query.return_value.filter.return_value.count.return_value = 0

    def _mock_get_db():
        yield db

    app.dependency_overrides[get_db] = _mock_get_db
    try:
        resp = client.get("/catalog/909/derived_status", headers={"X-API-Key": VALID_KEY})
        assert resp.status_code == 200
        payload = resp.json()
        assert "Not enough extracted text" in payload["summary_blocked_reason"]
        assert "Not enough extracted text" in payload["topics_blocked_reason"]
        assert payload["agenda_not_generated_yet"] is True
    finally:
        del app.dependency_overrides[get_db]


def test_catalog_agenda_items_requires_api_key():
    resp = client.get("/catalog/909/agenda_items")
    assert resp.status_code == 401


def test_catalog_agenda_items_returns_404_for_missing_catalog():
    from api.main import get_db

    db = MagicMock()
    db.get.return_value = None

    def _mock_get_db():
        yield db

    app.dependency_overrides[get_db] = _mock_get_db
    try:
        resp = client.get("/catalog/909/agenda_items", headers={"X-API-Key": VALID_KEY})
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Document not found"
    finally:
        del app.dependency_overrides[get_db]


def test_catalog_agenda_items_returns_empty_list_for_catalog_without_items():
    from api.main import get_db

    db = MagicMock()
    db.get.return_value = MagicMock(id=909)
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []

    def _mock_get_db():
        yield db

    app.dependency_overrides[get_db] = _mock_get_db
    try:
        resp = client.get("/catalog/909/agenda_items", headers={"X-API-Key": VALID_KEY})
        assert resp.status_code == 200
        assert resp.json() == {"catalog_id": 909, "items": []}
    finally:
        del app.dependency_overrides[get_db]


def test_catalog_agenda_items_returns_ordered_minimal_payload():
    from api.main import get_db

    first_item = MagicMock(
        id=12,
        order=1,
        title="Approve project contract",
        description="Authorize amendment.",
        classification="Action",
        result="Passed",
        page_number=3,
        votes=[{"member": "A", "vote": "yes"}],
    )
    second_item = MagicMock(
        id=13,
        order=2,
        title="Receive report",
        description=None,
        classification=None,
        result=None,
        page_number=None,
        votes=None,
    )
    db = MagicMock()
    db.get.return_value = MagicMock(id=909)
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [first_item, second_item]

    def _mock_get_db():
        yield db

    app.dependency_overrides[get_db] = _mock_get_db
    try:
        resp = client.get("/catalog/909/agenda_items", headers={"X-API-Key": VALID_KEY})
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["catalog_id"] == 909
        assert payload["items"] == [
            {
                "id": 12,
                "order": 1,
                "title": "Approve project contract",
                "description": "Authorize amendment.",
                "classification": "Action",
                "result": "Passed",
                "page_number": 3,
                "votes": [{"member": "A", "vote": "yes"}],
                "source": "catalog_agenda_items",
            },
            {
                "id": 13,
                "order": 2,
                "title": "Receive report",
                "description": None,
                "classification": None,
                "result": None,
                "page_number": None,
                "votes": None,
                "source": "catalog_agenda_items",
            },
        ]
    finally:
        del app.dependency_overrides[get_db]


def test_catalog_agenda_items_preserves_segmentation_source_for_disclaimer():
    from api.main import get_db

    agenda_item = MagicMock(
        id=12,
        order=1,
        title="Approve project contract",
        description="Authorize amendment.",
        classification="Action",
        result="Passed",
        page_number=3,
        votes=None,
    )
    db = MagicMock()
    db.get.return_value = MagicMock(id=909, agenda_segmentation_status="complete")
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [agenda_item]

    def _mock_get_db():
        yield db

    app.dependency_overrides[get_db] = _mock_get_db
    try:
        resp = client.get("/catalog/909/agenda_items", headers={"X-API-Key": VALID_KEY})
        assert resp.status_code == 200
        assert resp.json()["items"][0]["source"] == "llm"
    finally:
        del app.dependency_overrides[get_db]


def test_derived_status_exposes_not_generated_flags():
    from api.main import get_db

    catalog = MagicMock(
        id=911,
        content=(
            "The council discussed zoning reform, transportation safety, budget allocations, "
            "housing permits, environmental review, public works timelines, and procurement policy updates. "
            "Members reviewed implementation milestones, staffing impacts, and fiscal tradeoffs."
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
        resp = client.get("/catalog/911/derived_status", headers={"X-API-Key": VALID_KEY})
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["summary_not_generated_yet"] is True
        assert payload["topics_not_generated_yet"] is True
        assert payload["agenda_not_generated_yet"] is True
        assert payload["summary_blocked_reason"] is None
        assert payload["topics_blocked_reason"] is None
    finally:
        del app.dependency_overrides[get_db]


def test_derived_status_marks_agenda_summary_stale_from_structured_items():
    from api.main import get_db
    from pipeline.models import AgendaItem, Document

    catalog = MagicMock(
        id=912,
        content=(
            "City council agenda includes housing, transportation, fiscal updates, public comment, "
            "and multiple action items for adoption and review."
        ),
        content_hash="content-hash",
        agenda_items_hash="stored-old-hash",
        summary="agenda summary",
        summary_source_hash="different-old-hash",
        topics=[],
        topics_source_hash=None,
        agenda_segmentation_status="complete",
        agenda_segmentation_item_count=1,
        agenda_segmentation_attempted_at=datetime(2026, 7, 25, 12, 45, tzinfo=UTC),
        agenda_segmentation_error=None,
    )
    db = MagicMock()
    db.get.return_value = catalog

    def _query_side_effect(model):
        query = MagicMock()
        if model is Document:
            query.filter_by.return_value.first.return_value = MagicMock(category="agenda")
        elif model is AgendaItem:
            query.filter_by.return_value.order_by.return_value.all.return_value = [
                MagicMock(order=1, title="Item 1", description="Desc", classification="Agenda", result="", page_number=1)
            ]
        return query

    db.query.side_effect = _query_side_effect

    def _mock_get_db():
        yield db

    app.dependency_overrides[get_db] = _mock_get_db
    try:
        resp = client.get("/catalog/912/derived_status", headers={"X-API-Key": VALID_KEY})
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["summary_is_stale"] is True
        assert payload["agenda_segmentation_attempted_at"] == "2026-07-25T12:45:00+00:00"
    finally:
        del app.dependency_overrides[get_db]


def test_derived_status_marks_empty_agenda_fallback_summary_fresh():
    from api.main import get_db
    from pipeline.models import AgendaItem, Document

    catalog = MagicMock(
        id=913,
        content="Extracted agenda text with no substantive agenda items.",
        content_hash="content-hash",
        agenda_items_hash=None,
        summary="Agenda segmentation completed, but no substantive agenda items were detected in the extracted text.",
        summary_source_hash="content-hash",
        topics=[],
        topics_source_hash=None,
        agenda_segmentation_status="empty",
        agenda_segmentation_item_count=0,
        agenda_segmentation_attempted_at=None,
        agenda_segmentation_error=None,
    )
    db = MagicMock()
    db.get.return_value = catalog

    def _query_side_effect(model):
        query = MagicMock()
        if model is Document:
            query.filter_by.return_value.first.return_value = MagicMock(category="agenda")
        elif model is AgendaItem:
            query.filter_by.return_value.order_by.return_value.all.return_value = []
        return query

    db.query.side_effect = _query_side_effect

    def _mock_get_db():
        yield db

    app.dependency_overrides[get_db] = _mock_get_db
    try:
        resp = client.get("/catalog/913/derived_status", headers={"X-API-Key": VALID_KEY})
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["summary_is_stale"] is False
        assert payload["summary_not_generated_yet"] is False
        assert payload["agenda_is_empty"] is True
        assert "agenda_segmentation_attempted_at" in payload
        assert payload["agenda_segmentation_attempted_at"] is None
    finally:
        del app.dependency_overrides[get_db]

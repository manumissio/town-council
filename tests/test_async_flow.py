import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
import sys
import os
import importlib
from kombu.exceptions import OperationalError

# Setup mocks for dependencies we don't want to load
sys.modules["llama_cpp"] = MagicMock()
sys.modules["redis"] = MagicMock()

# Note: We do NOT mock 'celery' here because we need to import types from it.
# We will patch the tasks dynamically.

from api.main import app, get_db
from pipeline import tasks

client = TestClient(app)
VALID_KEY = "dev_secret_key_change_me"


def test_api_task_routes_work_when_app_imported_as_main(monkeypatch):
    """
    Docker starts the API from /app/api as `uvicorn main:app`.
    """
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    api_dir = os.path.join(repo_root, "api")
    original_cwd = os.getcwd()
    original_path = list(sys.path)
    original_main_module = sys.modules.pop("main", None)

    try:
        monkeypatch.chdir(api_dir)
        sys.path.insert(0, api_dir)
        docker_main = importlib.import_module("main")
        docker_client = TestClient(docker_main.app)

        mock_catalog = MagicMock()
        mock_catalog.id = 1
        mock_catalog.content = (
            "City council meeting discussed budget updates and adopted multiple motions after public comment."
        )
        mock_catalog.summary = None

        mock_db = MagicMock()
        mock_db.get.return_value = mock_catalog
        docker_main.app.dependency_overrides[docker_main.get_db] = lambda: mock_db

        mock_task = MagicMock()
        mock_task.id = "docker-task-uuid"
        docker_main.generate_summary_task.delay = MagicMock(return_value=mock_task)

        response = docker_client.post("/summarize/1", headers={"X-API-Key": VALID_KEY})

        assert response.status_code == 200
        assert response.json()["status"] == "processing"
        assert response.json()["task_id"] == "docker-task-uuid"
        docker_main.generate_summary_task.delay.assert_called_once_with(1, force=False)

        content_response = docker_client.get("/catalog/1/content", headers={"X-API-Key": VALID_KEY})

        assert content_response.status_code == 200
        assert content_response.json()["catalog_id"] == 1
        assert "budget updates" in content_response.json()["content"]

        lineage_rows = [
            (
                MagicMock(id=1, lineage_id="lin-1", lineage_confidence=0.9, lineage_updated_at=None, summary="Summary"),
                MagicMock(),
                MagicMock(name="Meeting A", record_date=MagicMock(isoformat=lambda: "2026-04-01")),
                MagicMock(display_name="Springfield", name="springfield"),
            )
        ]
        docker_main._lineage_rows = MagicMock(return_value=lineage_rows)

        lineage_response = docker_client.get("/lineage/lin-1")

        assert lineage_response.status_code == 200
        assert lineage_response.json()["lineage_id"] == "lin-1"
        docker_main._lineage_rows.assert_called_once()
    finally:
        if "docker_main" in locals():
            docker_main.app.dependency_overrides.clear()
        sys.modules.pop("main", None)
        if original_main_module is not None:
            sys.modules["main"] = original_main_module
        sys.path[:] = original_path
        os.chdir(original_cwd)

def test_async_summarization_flow(mocker):
    """
    Test: Does the /summarize endpoint return a Task ID instantly?
    """
    # 1. Mock DB to return a catalog item
    mock_catalog = MagicMock()
    mock_catalog.id = 1
    mock_catalog.content = "City council meeting discussed budget updates and adopted multiple motions after public comment."
    mock_catalog.summary = None # Not cached yet
    
    mock_db = MagicMock()
    mock_db.get.return_value = mock_catalog
    
    app.dependency_overrides[get_db] = lambda: mock_db
    
    # 2. Mock Celery Task
    # We need to mock the 'delay' method of the imported task
    mock_task = MagicMock()
    mock_task.id = "test-task-uuid"
    
    # Patch the task in the API module where it is imported
    with patch("api.main.generate_summary_task") as mock_generate_task:
        mock_generate_task.delay.return_value = mock_task
        
        # 3. Action: Call the API
        response = client.post(
            "/summarize/1", 
            headers={"X-API-Key": VALID_KEY}
        )
        
        # 4. Verify
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "processing"
        assert data["task_id"] == "test-task-uuid"
        assert "/tasks/test-task-uuid" in data["poll_url"]
        
        # Ensure the task was actually called
        mock_generate_task.delay.assert_called_once_with(1, force=False)
        
    del app.dependency_overrides[get_db]


def test_async_summarization_returns_503_when_enqueue_fails(mocker):
    mock_catalog = MagicMock()
    mock_catalog.id = 1
    mock_catalog.content = "City council meeting discussed budget updates and adopted multiple motions after public comment."
    mock_catalog.summary = None

    mock_db = MagicMock()
    mock_db.get.return_value = mock_catalog
    app.dependency_overrides[get_db] = lambda: mock_db

    with patch("api.main.generate_summary_task") as mock_generate_task:
        mock_generate_task.delay.side_effect = OperationalError("broker down")

        response = client.post("/summarize/1", headers={"X-API-Key": VALID_KEY})

        assert response.status_code == 503
        assert response.json()["detail"] == "Task queue unavailable"

    del app.dependency_overrides[get_db]


def test_async_summarization_returns_503_when_enqueue_times_out(mocker):
    mock_catalog = MagicMock()
    mock_catalog.id = 1
    mock_catalog.content = "City council meeting discussed budget updates and adopted multiple motions after public comment."
    mock_catalog.summary = None

    mock_db = MagicMock()
    mock_db.get.return_value = mock_catalog
    app.dependency_overrides[get_db] = lambda: mock_db

    with patch("api.main.generate_summary_task") as mock_generate_task:
        mock_generate_task.delay.side_effect = TimeoutError("broker timed out")

        response = client.post("/summarize/1", headers={"X-API-Key": VALID_KEY})

        assert response.status_code == 503
        assert response.json()["detail"] == "Task queue unavailable"

    del app.dependency_overrides[get_db]


def test_async_summarization_returns_503_when_task_id_missing(mocker):
    mock_catalog = MagicMock()
    mock_catalog.id = 1
    mock_catalog.content = "City council meeting discussed budget updates and adopted multiple motions after public comment."
    mock_catalog.summary = None

    mock_db = MagicMock()
    mock_db.get.return_value = mock_catalog
    app.dependency_overrides[get_db] = lambda: mock_db

    with patch("api.main.generate_summary_task") as mock_generate_task:
        mock_task = MagicMock()
        mock_task.id = ""
        mock_generate_task.delay.return_value = mock_task

        response = client.post("/summarize/1", headers={"X-API-Key": VALID_KEY})

        assert response.status_code == 503
        assert response.json()["detail"] == "Task queue unavailable"

    del app.dependency_overrides[get_db]


def test_async_summarization_does_not_mask_unexpected_enqueue_error(mocker):
    mock_catalog = MagicMock()
    mock_catalog.id = 1
    mock_catalog.content = "City council meeting discussed budget updates and adopted multiple motions after public comment."
    mock_catalog.summary = None

    mock_db = MagicMock()
    mock_db.get.return_value = mock_catalog
    app.dependency_overrides[get_db] = lambda: mock_db

    with patch("api.main.generate_summary_task") as mock_generate_task:
        mock_generate_task.delay.side_effect = ValueError("programmer error")

        response = client.post("/summarize/1", headers={"X-API-Key": VALID_KEY})

        assert response.status_code == 500
        assert response.json()["detail"] == "Internal Server Error. Our team has been notified."

    del app.dependency_overrides[get_db]


def test_task_status_polling():
    """
    Test: Does the polling endpoint return the task status?
    """
    # Mock AsyncResult within api.main
    with patch("api.main.AsyncResult") as MockResult:
        # Case 1: Processing
        mock_pending = MagicMock()
        mock_pending.ready.return_value = False
        MockResult.return_value = mock_pending
        
        resp = client.get("/tasks/00000000-0000-0000-0000-000000000001")
        assert resp.json()["status"] == "processing"
        
        # Case 2: Complete
        mock_done = MagicMock()
        mock_done.ready.return_value = True
        mock_done.result = {"summary": "Done."}
        MockResult.return_value = mock_done
        
        resp = client.get("/tasks/00000000-0000-0000-0000-000000000002")
        assert resp.json()["status"] == "complete"
        assert resp.json()["result"]["summary"] == "Done."


def test_generate_summary_retries_when_ai_returns_none(mocker):
    """
    Regression: if LocalAI returns None, task should trigger Celery retry.
    """
    mock_db = MagicMock()
    mock_catalog = MagicMock()
    mock_catalog.content = "City council meeting discussed budget updates and adopted multiple motions after public comment."
    mock_catalog.summary = None
    mock_db.get.return_value = mock_catalog

    mocker.patch.object(tasks, "SessionLocal", return_value=mock_db)
    mock_ai = MagicMock()
    mock_ai.summarize.return_value = None
    mocker.patch.object(tasks, "LocalAI", return_value=mock_ai)

    retry_exc = RuntimeError("retry-called")
    retry_mock = mocker.patch.object(tasks.generate_summary_task, "retry", side_effect=retry_exc)

    with pytest.raises(RuntimeError, match="retry-called"):
        tasks.generate_summary_task.run(1)

    retry_mock.assert_called_once()
    mock_db.rollback.assert_called_once()


def test_summarize_requires_api_key(mocker):
    """Protected endpoint should reject missing API key."""
    mock_catalog = MagicMock()
    mock_catalog.id = 1
    mock_catalog.content = "City council meeting discussed budget updates and adopted multiple motions after public comment."
    mock_catalog.summary = None

    mock_db = MagicMock()
    mock_db.get.return_value = mock_catalog
    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        response = client.post("/summarize/1")
        assert response.status_code == 401
    finally:
        del app.dependency_overrides[get_db]


def test_summarize_rejects_invalid_api_key(mocker):
    """Protected endpoint should reject incorrect API key."""
    mock_catalog = MagicMock()
    mock_catalog.id = 1
    mock_catalog.content = "City council meeting discussed budget updates and adopted multiple motions after public comment."
    mock_catalog.summary = None

    mock_db = MagicMock()
    mock_db.get.return_value = mock_catalog
    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        response = client.post("/summarize/1", headers={"X-API-Key": "wrong-key"})
        assert response.status_code == 401
    finally:
        del app.dependency_overrides[get_db]


def test_segment_returns_cached_items_when_quality_is_good():
    """
    Cached agenda should be reused when items look valid.
    """
    mock_catalog = MagicMock()
    mock_catalog.id = 1
    mock_catalog.content = "Agenda text"

    good_item = MagicMock()
    good_item.title = "1. Budget Amendment"
    good_item.page_number = 3

    mock_query = MagicMock()
    mock_query.filter_by.return_value.order_by.return_value.all.return_value = [good_item]

    mock_db = MagicMock()
    mock_db.get.return_value = mock_catalog
    mock_db.query.return_value = mock_query
    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        with patch("api.main.segment_agenda_task") as mock_segment_task:
            response = client.post("/segment/1", headers={"X-API-Key": VALID_KEY})
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "cached"
            mock_segment_task.delay.assert_not_called()
    finally:
        del app.dependency_overrides[get_db]


def test_segment_regenerates_when_cached_items_look_low_quality():
    """
    Low-quality cached agenda should trigger async regeneration.
    """
    mock_catalog = MagicMock()
    mock_catalog.id = 1
    mock_catalog.content = "Agenda text"

    low_quality_item_1 = MagicMock()
    low_quality_item_1.title = "Special Closed Meeting 10/03/11"
    low_quality_item_1.page_number = 1
    low_quality_item_2 = MagicMock()
    low_quality_item_2.title = "P R O C L A M A T I O N"
    low_quality_item_2.page_number = 1

    mock_query = MagicMock()
    mock_query.filter_by.return_value.order_by.return_value.all.return_value = [low_quality_item_1, low_quality_item_2]

    mock_db = MagicMock()
    mock_db.get.return_value = mock_catalog
    mock_db.query.return_value = mock_query
    app.dependency_overrides[get_db] = lambda: mock_db

    fake_task = MagicMock()
    fake_task.id = "regen-task-id"

    try:
        with patch("api.main.segment_agenda_task") as mock_segment_task, patch(
            "api.main.agenda_items_look_low_quality", return_value=True
        ):
            mock_segment_task.delay.return_value = fake_task

            response = client.post("/segment/1", headers={"X-API-Key": VALID_KEY})
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "processing"
            assert data["task_id"] == "regen-task-id"
            mock_segment_task.delay.assert_called_once_with(1)
    finally:
        del app.dependency_overrides[get_db]


def test_segment_task_keeps_page_number_in_results(mocker):
    """
    Regression: async segmentation should persist and return page_number.
    """
    mock_db = MagicMock()
    mock_catalog = MagicMock()
    mock_catalog.content = "Agenda text"
    mock_db.get.return_value = mock_catalog

    mock_doc = MagicMock()
    mock_doc.event_id = 42
    mock_doc_query = MagicMock()
    mock_doc_query.filter_by.return_value.first.return_value = mock_doc

    def query_side_effect(model):
        if model is tasks.Document:
            return mock_doc_query
        return MagicMock()

    mock_db.query.side_effect = query_side_effect

    mocker.patch.object(tasks, "SessionLocal", return_value=mock_db)
    mocker.patch.object(tasks, "LocalAI", return_value=MagicMock())
    mocker.patch.object(tasks, "resolve_agenda_items", return_value={
        "items": [{
            "order": 1,
            "title": "Budget Amendment",
            "description": "Approve revised allocations",
            "classification": "Agenda Item",
            "result": "",
            "page_number": 7,
            "legistar_matter_id": 321,
        }],
        "source_used": "legistar",
        "quality_score": 82,
        "confidence": "high",
    })

    result = tasks.segment_agenda_task.run(1)

    assert result["status"] == "complete"
    assert result["item_count"] == 1
    assert result["items"][0]["page_number"] == 7
    assert result["source_used"] == "legistar"


def test_segment_task_reindexes_catalog_after_success(mocker):
    mock_db = MagicMock()
    mock_catalog = MagicMock()
    mock_catalog.content = "Agenda text"
    mock_db.get.return_value = mock_catalog

    mock_doc = MagicMock()
    mock_doc.event_id = 42
    mock_doc_query = MagicMock()
    mock_doc_query.filter_by.return_value.first.return_value = mock_doc

    def query_side_effect(model):
        if model is tasks.Document:
            return mock_doc_query
        return MagicMock()

    mock_db.query.side_effect = query_side_effect

    mocker.patch.object(tasks, "SessionLocal", return_value=mock_db)
    mocker.patch.object(tasks, "LocalAI", return_value=MagicMock())
    mocker.patch.object(tasks, "resolve_agenda_items", return_value={
        "items": [{
            "order": 1,
            "title": "Budget Amendment",
            "description": "Approve revised allocations",
            "classification": "Agenda Item",
            "result": "",
            "page_number": 7,
            "legistar_matter_id": 321,
        }],
        "source_used": "legistar",
        "quality_score": 82,
        "confidence": "high",
    })
    reindex = mocker.patch.object(tasks, "reindex_catalog")

    tasks.segment_agenda_task.run(1)

    reindex.assert_called_once_with(1)


def test_segment_task_classification_failure_persists_failed_status(mocker):
    mock_db = MagicMock()
    mock_catalog = MagicMock()
    mock_catalog.content = "Agenda text"
    mock_db.get.return_value = mock_catalog

    mock_doc = MagicMock()
    mock_doc.event_id = 42
    mock_doc_query = MagicMock()
    mock_doc_query.filter_by.return_value.first.return_value = mock_doc

    def query_side_effect(model):
        if model is tasks.Document:
            return mock_doc_query
        return MagicMock()

    mock_db.query.side_effect = query_side_effect

    mocker.patch.object(tasks, "SessionLocal", return_value=mock_db)
    mocker.patch.object(tasks, "LocalAI", return_value=MagicMock())
    mocker.patch.object(
        tasks,
        "classify_catalog_bad_content",
        return_value=MagicMock(reason="laserfiche_error_page_detected"),
    )

    result = tasks.segment_agenda_task.run(1)

    assert result == {"status": "error", "error": "laserfiche_error_page_detected"}
    assert mock_catalog.agenda_segmentation_status == "failed"
    assert mock_catalog.agenda_segmentation_item_count == 0
    assert mock_catalog.agenda_segmentation_error == "laserfiche_error_page_detected"
    assert mock_catalog.agenda_segmentation_attempted_at is not None
    mock_db.commit.assert_called_once()


def test_segment_task_vote_extraction_failure_is_non_gating(mocker):
    mock_db = MagicMock()
    mock_catalog = MagicMock()
    mock_catalog.id = 1
    mock_catalog.content = "Agenda text"
    mock_db.get.return_value = mock_catalog

    mock_doc = MagicMock()
    mock_doc.event_id = 42
    mock_doc_query = MagicMock()
    mock_doc_query.filter_by.return_value.first.return_value = mock_doc

    created_item = MagicMock()
    created_item.title = "Budget Amendment"
    created_item.description = "Approve revised allocations"
    created_item.order = 1
    created_item.classification = "Agenda Item"
    created_item.result = ""
    created_item.page_number = 7

    def query_side_effect(model):
        if model is tasks.Document:
            return mock_doc_query
        return MagicMock()

    mock_db.query.side_effect = query_side_effect

    mocker.patch.object(tasks, "SessionLocal", return_value=mock_db)
    mocker.patch.object(tasks, "LocalAI", return_value=MagicMock())
    mocker.patch.object(
        tasks,
        "resolve_agenda_items",
        return_value={
            "items": [{
                "order": 1,
                "title": "Budget Amendment",
                "description": "Approve revised allocations",
                "classification": "Agenda Item",
                "result": "",
                "page_number": 7,
            }],
            "source_used": "legistar",
            "quality_score": 82,
            "confidence": "high",
        },
    )
    mocker.patch.object(tasks, "persist_agenda_items", return_value=[created_item])
    mocker.patch.object(tasks, "ENABLE_VOTE_EXTRACTION", True)
    mocker.patch.object(tasks, "run_vote_extraction_for_catalog", side_effect=RuntimeError("vote parse failed"))

    result = tasks.segment_agenda_task.run(1)

    assert result["status"] == "complete"
    assert result["vote_extraction"]["status"] == "failed"
    assert result["vote_extraction"]["error"] == "RuntimeError"
    assert mock_catalog.agenda_segmentation_status == "complete"
    mock_db.commit.assert_called_once()


def test_segment_task_local_ai_config_error_persists_failed_status_without_retry(mocker):
    mock_db = MagicMock()
    mock_catalog = MagicMock()
    mock_catalog.content = "Agenda text"
    mock_db.get.return_value = mock_catalog

    mocker.patch.object(tasks, "SessionLocal", return_value=mock_db)
    mocker.patch.object(tasks, "LocalAI", side_effect=tasks.LocalAIConfigError("missing backend config"))
    retry = mocker.patch.object(tasks.segment_agenda_task, "retry")

    result = tasks.segment_agenda_task.run(1)

    assert result == {"status": "error", "error": "missing backend config"}
    retry.assert_not_called()
    mock_db.rollback.assert_called_once()
    assert mock_catalog.agenda_segmentation_status == "failed"
    assert mock_catalog.agenda_segmentation_item_count == 0
    assert mock_catalog.agenda_segmentation_error == "missing backend config"
    mock_db.commit.assert_called_once()


def test_segment_task_retryable_error_persists_failed_status_before_retry(mocker):
    mock_db = MagicMock()
    mock_catalog = MagicMock()
    mock_catalog.content = "Agenda text"
    mock_db.get.return_value = mock_catalog

    mock_doc = MagicMock()
    mock_doc.event_id = 42
    mock_doc_query = MagicMock()
    mock_doc_query.filter_by.return_value.first.return_value = mock_doc

    def query_side_effect(model):
        if model is tasks.Document:
            return mock_doc_query
        return MagicMock()

    mock_db.query.side_effect = query_side_effect

    mocker.patch.object(tasks, "SessionLocal", return_value=mock_db)
    mocker.patch.object(tasks, "LocalAI", return_value=MagicMock())
    mocker.patch.object(tasks, "resolve_agenda_items", side_effect=RuntimeError("resolver exploded"))
    retry_exc = RuntimeError("retry-called")
    retry = mocker.patch.object(tasks.segment_agenda_task, "retry", side_effect=retry_exc)

    with pytest.raises(RuntimeError, match="retry-called"):
        tasks.segment_agenda_task.run(1)

    retry.assert_called_once()
    mock_db.rollback.assert_called_once()
    assert mock_catalog.agenda_segmentation_status == "failed"
    assert mock_catalog.agenda_segmentation_item_count == 0
    assert mock_catalog.agenda_segmentation_error == "resolver exploded"
    mock_db.commit.assert_called_once()

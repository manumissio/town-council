from datetime import date
import importlib
import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from kombu.exceptions import OperationalError
from sqlalchemy.orm import sessionmaker

# Setup mocks for dependencies we don't want to load
sys.modules["llama_cpp"] = MagicMock()
sys.modules["redis"] = MagicMock()

# Note: We do NOT mock 'celery' here because we need to import types from it.
# We will patch the tasks dynamically.

from api.main import app, get_db
from pipeline import config, indexer, llm as llm_module, task_runtime, tasks
from pipeline.inference_provider_contract import InferenceProvider, ProviderResponseError
from pipeline.models import AgendaItem, Catalog, Document, Event, Place

client = TestClient(app)
VALID_KEY = "dev_secret_key_change_me"
AGENDA_PROVIDER_TEXT = "Budget Amendment (Page 7) - Approve revised allocations"


def _seed_agenda_catalog(
    db_session,
    *,
    catalog_id: int,
    content: str = "Agenda text for the city council budget amendment.",
    location: str | None = None,
    url: str | None = None,
) -> Catalog:
    place = Place(
        name=f"agenda-place-{catalog_id}",
        state="CA",
        ocd_division_id=f"ocd-division/country:us/state:ca/place:agenda-{catalog_id}",
    )
    event = Event(
        ocd_id=f"ocd-event/agenda-{catalog_id}",
        place=place,
        name="City Council",
        record_date=date(2026, 1, 10),
    )
    catalog = Catalog(
        id=catalog_id,
        url_hash=f"agenda-{catalog_id}",
        content=content,
        location=location,
        url=url,
        filename=f"agenda-{catalog_id}.pdf",
    )
    document = Document(
        place=place,
        event=event,
        catalog=catalog,
        category="agenda",
    )
    db_session.add_all([place, event, catalog, document])
    db_session.commit()
    return catalog


def _patch_task_session(mocker, shared_engine) -> None:
    task_db = sessionmaker(bind=shared_engine)()
    mocker.patch.object(task_runtime, "task_session", return_value=task_db)


def _patch_agenda_provider(
    mocker,
    *,
    agenda_text: str = AGENDA_PROVIDER_TEXT,
) -> MagicMock:
    agenda_provider = MagicMock(spec=InferenceProvider)
    agenda_provider.extract_agenda.return_value = agenda_text
    mocker.patch.object(llm_module, "get_runtime_provider", return_value=agenda_provider)
    return agenda_provider


def _patch_meilisearch_client(mocker) -> MagicMock:
    search_client = MagicMock()
    search_client.index.return_value.delete_documents.return_value = SimpleNamespace(
        task_uid=41
    )
    search_client.wait_for_task.return_value = SimpleNamespace(
        status="succeeded",
        error=None,
    )
    mocker.patch.object(indexer.meilisearch, "Client", return_value=search_client)
    return search_client


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

        mock_task = MagicMock(id="docker-task-uuid")
        with patch("api.task_dispatch.celery_app.send_task", return_value=mock_task) as send_task:
            response = docker_client.post("/summarize/1", headers={"X-API-Key": VALID_KEY})

        assert response.status_code == 200
        assert response.json()["status"] == "processing"
        assert response.json()["task_id"] == "docker-task-uuid"
        send_task.assert_called_once_with(
            "pipeline.tasks.generate_summary_task",
            args=(1,),
            kwargs={"force": False},
        )

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
        lineage_query = mock_db.query.return_value.join.return_value.join.return_value.join.return_value
        lineage_query.filter.return_value.order_by.return_value.all.return_value = lineage_rows

        lineage_response = docker_client.get("/lineage/lin-1")

        assert lineage_response.status_code == 200
        assert lineage_response.json()["lineage_id"] == "lin-1"
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
    
    mock_task = MagicMock()
    mock_task.id = "test-task-uuid"

    with patch("api.task_dispatch.celery_app.send_task", return_value=mock_task) as send_task:
        response = client.post(
            "/summarize/1", 
            headers={"X-API-Key": VALID_KEY}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "processing"
        assert data["task_id"] == "test-task-uuid"
        assert "/tasks/test-task-uuid" in data["poll_url"]
        send_task.assert_called_once_with(
            "pipeline.tasks.generate_summary_task",
            args=(1,),
            kwargs={"force": False},
        )
        
    del app.dependency_overrides[get_db]


def test_async_summarization_returns_503_when_enqueue_fails(mocker):
    mock_catalog = MagicMock()
    mock_catalog.id = 1
    mock_catalog.content = "City council meeting discussed budget updates and adopted multiple motions after public comment."
    mock_catalog.summary = None

    mock_db = MagicMock()
    mock_db.get.return_value = mock_catalog
    app.dependency_overrides[get_db] = lambda: mock_db

    with patch("api.task_dispatch.celery_app.send_task", side_effect=OperationalError("broker down")):

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

    with patch("api.task_dispatch.celery_app.send_task", side_effect=TimeoutError("broker timed out")):

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

    with patch("api.task_dispatch.celery_app.send_task") as send_task:
        mock_task = MagicMock()
        mock_task.id = ""
        send_task.return_value = mock_task

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

    with patch("api.task_dispatch.celery_app.send_task", side_effect=ValueError("programmer error")):

        response = client.post("/summarize/1", headers={"X-API-Key": VALID_KEY})

        assert response.status_code == 500
        assert response.json()["detail"] == "Internal Server Error. Our team has been notified."

    del app.dependency_overrides[get_db]


def test_task_status_polling():
    """
    Test: Does the polling endpoint return the task status?
    """
    with patch("api.task_route_support.AsyncResult") as MockResult:
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

    mocker.patch.object(task_runtime, "task_session", return_value=mock_db)
    summary_provider = MagicMock(spec=InferenceProvider)
    summary_provider.summarize_text.return_value = None
    mocker.patch.object(llm_module, "get_runtime_provider", return_value=summary_provider)

    retry_exc = RuntimeError("retry-called")
    retry_mock = mocker.patch.object(tasks.generate_summary_task, "retry", side_effect=retry_exc)

    with pytest.raises(RuntimeError, match="retry-called"):
        tasks.generate_summary_task.run(1)

    retry_mock.assert_called_once()
    assert retry_mock.call_args.kwargs["countdown"] == 60
    mock_db.rollback.assert_called_once()
    mock_db.close.assert_called_once()


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
        with patch("api.task_dispatch.celery_app.send_task") as send_task:
            response = client.post("/segment/1", headers={"X-API-Key": VALID_KEY})
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "cached"
            send_task.assert_not_called()
    finally:
        del app.dependency_overrides[get_db]


def test_segment_regenerates_when_cached_items_look_low_quality():
    """
    Low-quality cached agenda should trigger async regeneration.
    """
    mock_catalog = MagicMock()
    mock_catalog.id = 1
    mock_catalog.content = "Agenda text"

    low_quality_items = [
        SimpleNamespace(
            title="Special Closed Meeting 10/03/11",
            page_number=1,
            description=None,
            result=None,
        ),
        SimpleNamespace(
            title="P R O C L A M A T I O N",
            page_number=1,
            description=None,
            result=None,
        ),
        SimpleNamespace(
            title="Call to Order",
            page_number=1,
            description=None,
            result=None,
        ),
    ]

    mock_query = MagicMock()
    mock_query.filter_by.return_value.order_by.return_value.all.return_value = low_quality_items

    mock_db = MagicMock()
    mock_db.get.return_value = mock_catalog
    mock_db.query.return_value = mock_query
    app.dependency_overrides[get_db] = lambda: mock_db

    fake_task = MagicMock()
    fake_task.id = "regen-task-id"

    try:
        with patch("api.task_dispatch.celery_app.send_task", return_value=fake_task) as send_task:
            response = client.post("/segment/1", headers={"X-API-Key": VALID_KEY})
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "processing"
            assert data["task_id"] == "regen-task-id"
            send_task.assert_called_once_with(
                "pipeline.tasks.segment_agenda_task",
                args=(1,),
                kwargs={},
            )
    finally:
        del app.dependency_overrides[get_db]


def test_segment_task_keeps_page_number_in_results(mocker, db_session, shared_engine):
    _seed_agenda_catalog(db_session, catalog_id=1)
    _patch_task_session(mocker, shared_engine)
    _patch_agenda_provider(mocker)
    _patch_meilisearch_client(mocker)

    segmentation_result = tasks.segment_agenda_task.run(1)

    assert segmentation_result["status"] == "complete"
    assert segmentation_result["item_count"] == 1
    assert segmentation_result["items"][0]["page_number"] == 7
    assert segmentation_result["source_used"] == "llm"
    persisted_item = db_session.query(AgendaItem).filter_by(catalog_id=1).one()
    assert persisted_item.page_number == 7


def test_segment_task_marks_whitespace_only_items_empty(mocker, db_session, shared_engine):
    catalog = _seed_agenda_catalog(db_session, catalog_id=6)
    _patch_task_session(mocker, shared_engine)
    _patch_agenda_provider(mocker)
    mocker.patch(
        "pipeline.task_agenda_segmentation.agenda_resolver.resolve_agenda_items",
        return_value={
            "items": [{"order": 1, "title": "  \n  "}],
            "source_used": "llm",
            "quality_score": 50,
        },
    )

    segmentation_result = tasks.segment_agenda_task.run(6)

    assert segmentation_result["status"] == "empty"
    assert segmentation_result["item_count"] == 0
    db_session.refresh(catalog)
    assert catalog.agenda_segmentation_status == "empty"
    assert catalog.agenda_segmentation_item_count == 0
    assert db_session.query(AgendaItem).filter_by(catalog_id=6).count() == 0


def test_segment_task_reindexes_catalog_after_success(mocker, db_session, shared_engine):
    _seed_agenda_catalog(db_session, catalog_id=2)
    _patch_task_session(mocker, shared_engine)
    _patch_agenda_provider(mocker)
    search_client = _patch_meilisearch_client(mocker)

    segmentation_result = tasks.segment_agenda_task.run(2)

    assert segmentation_result["status"] == "complete"
    indexed_documents = search_client.index.return_value.add_documents.call_args.args[0]
    assert any(document["catalog_id"] == 2 for document in indexed_documents)


def test_segment_task_classification_failure_persists_failed_status(
    mocker,
    db_session,
    shared_engine,
    tmp_path,
):
    portal_path = tmp_path / "laserfiche.html"
    portal_path.write_text("not structured agenda html", encoding="utf-8")
    catalog = _seed_agenda_catalog(
        db_session,
        catalog_id=3,
        content=(
            "The system has encountered an error and could not complete your request. "
            "If the problem persists, please contact the site administrator."
        ),
        location=str(portal_path),
        url="https://portal.laserfiche.com/portal/DocView.aspx?id=3",
    )
    _patch_task_session(mocker, shared_engine)
    _patch_agenda_provider(mocker)

    segmentation_result = tasks.segment_agenda_task.run(3)

    assert segmentation_result == {"status": "error", "error": "laserfiche_error_page_detected"}
    db_session.refresh(catalog)
    assert catalog.agenda_segmentation_status == "failed"
    assert catalog.agenda_segmentation_item_count == 0
    assert catalog.agenda_segmentation_error == "laserfiche_error_page_detected"
    assert catalog.agenda_segmentation_attempted_at is not None


def test_segment_task_vote_provider_failure_is_non_gating(mocker, db_session, shared_engine):
    catalog = _seed_agenda_catalog(
        db_session,
        catalog_id=4,
        content=(
            "Budget Amendment. The council considered the revised allocation. "
            "A motion was made and seconded. The motion passed by a vote of five to zero. "
        )
        * 5,
    )
    _patch_task_session(mocker, shared_engine)
    agenda_provider = _patch_agenda_provider(mocker)
    mocker.patch.object(config, "ENABLE_VOTE_EXTRACTION", True)
    agenda_provider.generate_json.side_effect = ProviderResponseError("bad vote payload")
    _patch_meilisearch_client(mocker)

    segmentation_result = tasks.segment_agenda_task.run(4)

    assert segmentation_result["status"] == "complete"
    assert segmentation_result["vote_extraction"]["status"] == "complete"
    assert segmentation_result["vote_extraction"]["failed_items"] == 1
    assert agenda_provider.generate_json.called
    db_session.refresh(catalog)
    assert catalog.agenda_segmentation_status == "complete"


def test_segment_task_retryable_error_persists_failed_status_before_retry(mocker):
    catalog = Catalog(
        id=5,
        url_hash="agenda-retry-5",
        content="Agenda text",
    )
    task_db = MagicMock()
    task_db.get.side_effect = [RuntimeError("database unavailable"), catalog]
    mocker.patch.object(task_runtime, "task_session", return_value=task_db)
    _patch_agenda_provider(mocker)
    retry_error = RuntimeError("retry-called")
    retry = mocker.patch.object(tasks.segment_agenda_task, "retry", side_effect=retry_error)

    with pytest.raises(RuntimeError, match="retry-called"):
        tasks.segment_agenda_task.run(5)

    assert str(retry.call_args.kwargs["exc"]) == "database unavailable"
    assert retry.call_args.kwargs["countdown"] == 60
    assert task_db.rollback.call_count == 1
    assert catalog.agenda_segmentation_status == "failed"
    assert catalog.agenda_segmentation_item_count == 0
    assert catalog.agenda_segmentation_error == "database unavailable"
    task_db.commit.assert_called_once()
    task_db.close.assert_called_once()

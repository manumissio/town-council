import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
import sys
import os

# Setup mocks for dependencies we don't want to load
sys.modules["llama_cpp"] = MagicMock()
sys.modules["redis"] = MagicMock()

# Note: We do NOT mock 'celery' here because we need to import types from it.
# We will patch the tasks dynamically.

from api.main import app, get_db

client = TestClient(app)
VALID_KEY = "dev_secret_key_change_me"

def test_async_summarization_flow(mocker):
    """
    Test: Does the /summarize endpoint return a Task ID instantly?
    """
    # 1. Mock DB to return a catalog item
    mock_catalog = MagicMock()
    mock_catalog.id = 1
    mock_catalog.content = "Some text content"
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
        mock_generate_task.delay.assert_called_once_with(1)
        
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
        
        resp = client.get("/tasks/pending-id")
        assert resp.json()["status"] == "processing"
        
        # Case 2: Complete
        mock_done = MagicMock()
        mock_done.ready.return_value = True
        mock_done.result = {"summary": "Done."}
        MockResult.return_value = mock_done
        
        resp = client.get("/tasks/done-id")
        assert resp.json()["status"] == "complete"
        assert resp.json()["result"]["summary"] == "Done."
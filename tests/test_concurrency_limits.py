import pytest
import threading
import time
from fastapi.testclient import TestClient
from unittest.mock import MagicMock
import sys
import os

# Ensure llama_cpp is mocked
sys.modules["llama_cpp"] = MagicMock()

from api.main import app, get_db
from pipeline.llm import LocalAI
import pipeline.llm as llm_module

client = TestClient(app)
VALID_KEY = "dev_secret_key_change_me"

def test_batch_limit_protection():
    """
    Test: Does the API reject excessively large batch requests?
    """
    large_id_list = list(range(1, 52))
    params = {"ids": large_id_list}
    
    app.dependency_overrides[get_db] = lambda: MagicMock()
    
    try:
        response = client.get("/catalog/batch", params=params, headers={"X-API-Key": VALID_KEY})
        assert response.status_code == 400
        assert "Batch request too large" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_catalog_batch_returns_meeting_summary_shape():
    db = MagicMock()
    catalog = MagicMock(id=7, filename="packet.pdf")
    event = MagicMock()
    event.name = "Council Meeting"
    event.record_date.isoformat.return_value = "2026-04-17"
    place = MagicMock(display_name="Springfield", name="springfield")
    query = db.query.return_value
    query.join.return_value.join.return_value.join.return_value.filter.return_value.all.return_value = [
        (catalog, MagicMock(), event, place)
    ]
    app.dependency_overrides[get_db] = lambda: db

    try:
        response = client.get("/catalog/batch", params={"ids": [7]}, headers={"X-API-Key": VALID_KEY})

        assert response.status_code == 200
        assert response.json() == [
            {
                "id": 7,
                "filename": "packet.pdf",
                "title": "Council Meeting",
                "date": "2026-04-17",
                "city": "Springfield",
            }
        ]
    finally:
        app.dependency_overrides.clear()


def test_ai_concurrency_lock(monkeypatch):
    """
    Test: Does the LocalAI summarize method use the internal lock?
    """
    # 1. Reset Singleton
    monkeypatch.setattr(llm_module, "LOCAL_AI_BACKEND", "inprocess")
    LocalAI._instance = None
    ai = LocalAI()
    
    # 2. Setup mock lock and mock llm
    mock_lock = MagicMock()
    mock_llm = MagicMock()
    mock_llm.return_value = {"choices": [{"text": "result"}]}
    
    # 3. Inject mocks
    ai._lock = mock_lock
    ai.llm = mock_llm
    ai._load_model = lambda: None
    
    # 4. Action
    ai.summarize("test")
    
    # 5. Verify
    assert mock_lock.__enter__.called
    assert mock_lock.__exit__.called
    assert mock_llm.called

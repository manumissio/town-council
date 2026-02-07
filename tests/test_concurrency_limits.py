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

def test_ai_concurrency_lock():
    """
    Test: Does the LocalAI summarize method use the internal lock?
    """
    # 1. Reset Singleton
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
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
import sys
import os
import json

# Setup mocks
sys.modules["llama_cpp"] = MagicMock()
sys.modules["redis"] = MagicMock() # Mock redis for tests

from api.main import app, get_db
from api.cache import cached

client = TestClient(app)
VALID_KEY = "dev_secret_key_change_me"

def test_cache_decorator():
    """
    Test: Does the cache decorator actually cache results?
    """
    mock_redis = MagicMock()
    
    # 1. First call: Cache miss
    mock_redis.get.return_value = None
    
    # Define a fake function to cache
    call_count = 0
    @cached(expire=60, key_prefix="test")
    def expensive_func(arg):
        nonlocal call_count
        call_count += 1
        return {"data": arg}
    
    # Patch the redis_client used inside the decorator
    with patch('api.cache.redis_client', mock_redis):
        # First call
        result1 = expensive_func("foo")
        assert result1 == {"data": "foo"}
        assert call_count == 1
        mock_redis.setex.assert_called_once()
        
        # 2. Second call: Cache hit
        mock_redis.get.return_value = json.dumps({"data": "foo"})
        result2 = expensive_func("foo")
        assert result2 == {"data": "foo"}
        assert call_count == 1 # Function NOT called again

def test_pagination_defaults():
    """
    Test: Does the /people endpoint enforce pagination limits?
    """
    # Mock DB query
    mock_query = MagicMock()
    mock_query.count.return_value = 100
    mock_query.order_by.return_value.limit.return_value.offset.return_value.all.return_value = []
    
    mock_db = MagicMock()
    mock_db.query.return_value = mock_query
    
    app.dependency_overrides[get_db] = lambda: mock_db
    
    try:
        # 1. Default limit (should be 50)
        client.get("/people")
        mock_query.order_by.return_value.limit.assert_called_with(50)
        
        # 2. Custom limit (should respect valid value)
        client.get("/people?limit=10")
        mock_query.order_by.return_value.limit.assert_called_with(10)
        
        # 3. Invalid limit (should default or error, FastAPI handles validation)
        response = client.get("/people?limit=1000")
        # FastAPI validation error
        assert response.status_code == 422 
        
    finally:
        del app.dependency_overrides[get_db]

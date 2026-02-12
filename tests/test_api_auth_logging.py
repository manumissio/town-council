import logging
from unittest.mock import MagicMock
import os
import sys

from fastapi.testclient import TestClient

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "api"))
sys.modules["llama_cpp"] = MagicMock()

from api.main import app


client = TestClient(app)


def test_unauthorized_request_log_does_not_include_api_key(caplog):
    caplog.set_level(logging.WARNING, logger="town-council-api")
    leaked_key = "my_really_secret_key"

    response = client.post("/segment/401", headers={"X-API-Key": leaked_key})

    assert response.status_code == 401
    all_logs = " ".join(record.getMessage() for record in caplog.records)
    assert "Unauthorized API access attempt" in all_logs
    assert leaked_key not in all_logs

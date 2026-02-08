import sys
import os
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient


# Add repo root + api to import path (matches existing test_api.py style)
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "api"))

# Avoid compiled llama dependency during tests.
sys.modules["llama_cpp"] = MagicMock()


def test_metrics_endpoint_exposes_prometheus_payload():
    from api.main import app

    client = TestClient(app)
    resp = client.get("/metrics")
    assert resp.status_code == 200
    # We only assert metric names exist; values are non-deterministic.
    body = resp.text
    assert "tc_http_requests_total" in body
    assert "tc_http_request_duration_seconds" in body
    assert "tc_http_requests_in_flight" in body


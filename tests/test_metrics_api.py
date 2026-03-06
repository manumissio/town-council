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


def test_metrics_endpoint_survives_partial_redis_provider_metric_failures(monkeypatch):
    """
    Regression: provider-metrics collector errors should degrade confidence, not break /metrics.
    """
    from api.main import app
    import pipeline.metrics as worker_metrics

    class _BrokenRedis:
        def scan_iter(self, match=None):
            _ = match
            raise RuntimeError("scan failure")

    monkeypatch.setattr(worker_metrics, "_REDIS_INIT", True)
    monkeypatch.setattr(worker_metrics, "_REDIS_BACKEND_UP", 1.0)
    monkeypatch.setattr(worker_metrics, "_REDIS_CLIENT", _BrokenRedis())

    client = TestClient(app)
    resp = client.get("/metrics")
    assert resp.status_code == 200
    body = resp.text
    assert "tc_http_requests_total" in body
    # API metrics endpoint should remain available even if worker-provider Redis reads degrade.

import importlib

import pytest
from prometheus_client import generate_latest

from pipeline import metrics, metrics_redis_backend


def _sample_value(metric, sample_name: str, expected_labels: dict[str, str]) -> float | None:
    for sample in metric.samples:
        if sample.name != sample_name:
            continue
        if all(sample.labels.get(k) == v for k, v in expected_labels.items()):
            return float(sample.value)
    return None


class _FakeRedis:
    def __init__(self):
        self.kv = {
            "tc:provider:req_total:http:summarize_text:gemma-3-270m-custom:ok": "5",
            "tc:provider:prompt_tokens_total:http:summarize_text:gemma-3-270m-custom:ok": "120",
            "tc:provider:completion_tokens_total:http:summarize_text:gemma-3-270m-custom:ok": "80",
        }
        self.hashes = {
            "tc:provider:ttft_ms:bucket:http:summarize_text:gemma-3-270m-custom:ok": {"100.0": "2", "250.0": "3"},
            "tc:provider:ttft_ms:meta:http:summarize_text:gemma-3-270m-custom:ok": {"count": "3", "sum": "530"},
            "tc:provider:tps:bucket:http:summarize_text:gemma-3-270m-custom:ok": {"10.0": "2", "20.0": "3"},
            "tc:provider:tps:meta:http:summarize_text:gemma-3-270m-custom:ok": {"count": "3", "sum": "47.5"},
        }

    def scan_iter(self, match=None):
        keys = list(self.kv.keys()) + list(self.hashes.keys())
        if match is None:
            for key in keys:
                yield key
            return
        prefix = match.rstrip("*")
        for key in keys:
            if key.startswith(prefix):
                yield key

    def get(self, key):
        return self.kv.get(key)

    def incrby(self, key, amount):
        self.kv[key] = int(self.kv.get(key, 0)) + int(amount)

    def hgetall(self, key):
        return self.hashes.get(key, {})


def test_collector_describes_every_redis_backed_metric(monkeypatch):
    mod = importlib.import_module("pipeline.metrics")
    monkeypatch.setattr(metrics_redis_backend, "_REDIS_INIT", True)
    monkeypatch.setattr(metrics_redis_backend, "_REDIS_BACKEND_UP", 1.0)
    monkeypatch.setattr(metrics_redis_backend, "_REDIS_CLIENT", _FakeRedis())

    collector = mod.RedisProviderMetricsCollector()
    described_names = {metric.name for metric in collector.describe()}
    collected_names = {metric.name for metric in collector.collect()}

    assert described_names == collected_names
    assert described_names == {
        "tc_provider_metrics_backend_up",
        "tc_provider_requests",
        "tc_provider_timeouts",
        "tc_provider_retries",
        "tc_provider_prompt_tokens",
        "tc_provider_completion_tokens",
        "tc_provider_ttft_ms",
        "tc_provider_tokens_per_sec",
    }


def test_provider_series_have_one_registry_owner(monkeypatch):
    fake = _FakeRedis()
    model = "registry-ownership-probe"
    monkeypatch.setattr(metrics_redis_backend, "_REDIS_INIT", True)
    monkeypatch.setattr(metrics_redis_backend, "_REDIS_BACKEND_UP", 1.0)
    monkeypatch.setattr(metrics_redis_backend, "_REDIS_CLIENT", fake)

    metrics.record_provider_request(
        "http",
        "summarize_text",
        model,
        "ok",
        1.0,
    )
    exposition = generate_latest().decode()
    exposition_lines = exposition.splitlines()
    matching_series = [
        line
        for line in exposition_lines
        if line.startswith("tc_provider_requests_total{")
        and f'model="{model}"' in line
    ]

    assert len(matching_series) == 1
    assert exposition.count("# HELP tc_provider_requests_total ") == 1
    assert exposition.count("# TYPE tc_provider_requests_total counter") == 1
    assert "tc_provider_requests_total_total" not in exposition


def test_redis_unavailable_scrape_uses_local_provider_series(monkeypatch):
    model = "redis-unavailable-probe"
    labels = {
        "provider": "http",
        "operation": "summarize_text",
        "model": model,
        "outcome": "ok",
    }
    monkeypatch.setattr(metrics_redis_backend, "_REDIS_INIT", True)
    monkeypatch.setattr(metrics_redis_backend, "_REDIS_BACKEND_UP", 0.0)
    monkeypatch.setattr(metrics_redis_backend, "_REDIS_CLIENT", None)

    metrics.record_provider_request(
        "http",
        "summarize_text",
        model,
        "ok",
        1.0,
    )
    collected_metrics = {
        collected_metric.name: collected_metric
        for collected_metric in metrics.RedisProviderMetricsCollector().collect()
    }

    assert (
        _sample_value(
            collected_metrics["tc_provider_requests"],
            "tc_provider_requests_total",
            labels,
        )
        == 1.0
    )


def test_redis_collector_exports_provider_series(monkeypatch):
    mod = importlib.import_module("pipeline.metrics")
    monkeypatch.setattr(metrics_redis_backend, "_REDIS_INIT", True)
    monkeypatch.setattr(metrics_redis_backend, "_REDIS_BACKEND_UP", 1.0)
    monkeypatch.setattr(metrics_redis_backend, "_REDIS_CLIENT", _FakeRedis())

    collector = mod.RedisProviderMetricsCollector()
    metrics = {m.name: m for m in collector.collect()}

    labels = {
        "provider": "http",
        "operation": "summarize_text",
        "model": "gemma-3-270m-custom",
        "outcome": "ok",
    }
    assert "tc_provider_requests" in metrics
    assert _sample_value(metrics["tc_provider_requests"], "tc_provider_requests_total", labels) == 5.0
    assert _sample_value(metrics["tc_provider_prompt_tokens"], "tc_provider_prompt_tokens_total", labels) == 120.0
    assert (
        _sample_value(metrics["tc_provider_completion_tokens"], "tc_provider_completion_tokens_total", labels)
        == 80.0
    )
    assert (
        _sample_value(
            metrics["tc_provider_ttft_ms"],
            "tc_provider_ttft_ms_count",
            labels,
        )
        == 3.0
    )
    assert (
        _sample_value(
            metrics["tc_provider_tokens_per_sec"],
            "tc_provider_tokens_per_sec_count",
            labels,
        )
        == 3.0
    )


def test_redis_collector_backend_gauge_reflects_degraded_state(monkeypatch):
    mod = importlib.import_module("pipeline.metrics")
    monkeypatch.setattr(metrics_redis_backend, "_REDIS_INIT", True)
    monkeypatch.setattr(metrics_redis_backend, "_REDIS_BACKEND_UP", 0.0)
    monkeypatch.setattr(metrics_redis_backend, "_REDIS_CLIENT", _FakeRedis())

    collector = mod.RedisProviderMetricsCollector()
    metrics = {m.name: m for m in collector.collect()}
    backend_metric = metrics["tc_provider_metrics_backend_up"]
    value = _sample_value(backend_metric, "tc_provider_metrics_backend_up", {})
    assert value == 0.0


def test_redis_collector_uses_backend_client_patch(monkeypatch):
    mod = importlib.import_module("pipeline.metrics")
    fake = _FakeRedis()
    monkeypatch.setattr(metrics_redis_backend, "_redis_client", lambda: fake)
    monkeypatch.setattr(metrics_redis_backend, "_REDIS_BACKEND_UP", 1.0)

    collector = mod.RedisProviderMetricsCollector()
    metrics = {m.name: m for m in collector.collect()}

    labels = {
        "provider": "http",
        "operation": "summarize_text",
        "model": "gemma-3-270m-custom",
        "outcome": "ok",
    }
    assert _sample_value(metrics["tc_provider_requests"], "tc_provider_requests_total", labels) == 5.0


def test_redis_collector_handles_scan_errors_without_raising(monkeypatch):
    mod = importlib.import_module("pipeline.metrics")
    model = "redis-read-error-probe"
    labels = {
        "provider": "http",
        "operation": "summarize_text",
        "model": model,
        "outcome": "ok",
    }

    class _BrokenRedis:
        def scan_iter(self, match=None):
            _ = match
            raise RuntimeError("scan failed")

    metrics.PROVIDER_REQUESTS_TOTAL.labels(**labels).inc()
    monkeypatch.setattr(metrics_redis_backend, "_REDIS_INIT", True)
    monkeypatch.setattr(metrics_redis_backend, "_REDIS_BACKEND_UP", 1.0)
    monkeypatch.setattr(metrics_redis_backend, "_REDIS_CLIENT", _BrokenRedis())

    collector = mod.RedisProviderMetricsCollector()
    collected_metrics = {
        collected_metric.name: collected_metric
        for collected_metric in collector.collect()
    }
    names = list(collected_metrics)
    assert "tc_provider_metrics_backend_up" in names
    assert (
        _sample_value(
            collected_metrics["tc_provider_requests"],
            "tc_provider_requests_total",
            labels,
        )
        == 1.0
    )
    assert metrics_redis_backend._REDIS_BACKEND_UP == 0.0


def test_redis_write_error_scrape_uses_local_provider_series(monkeypatch):
    model = "redis-write-error-probe"
    labels = {
        "provider": "http",
        "operation": "summarize_text",
        "model": model,
        "outcome": "ok",
    }

    class _WriteFailingRedis:
        def incrby(self, key, amount):
            raise RuntimeError(f"write failed for {key}:{amount}")

        def scan_iter(self, match=None):
            _ = match
            return iter(())

        def hgetall(self, key):
            _ = key
            return {}

    monkeypatch.setattr(metrics_redis_backend, "_REDIS_INIT", True)
    monkeypatch.setattr(metrics_redis_backend, "_REDIS_BACKEND_UP", 1.0)
    monkeypatch.setattr(metrics_redis_backend, "_REDIS_CLIENT", _WriteFailingRedis())

    metrics.record_provider_request(
        "http",
        "summarize_text",
        model,
        "ok",
        1.0,
    )
    collected_metrics = {
        collected_metric.name: collected_metric
        for collected_metric in metrics.RedisProviderMetricsCollector().collect()
    }

    assert metrics_redis_backend._REDIS_BACKEND_UP == 0.0
    assert (
        _sample_value(
            collected_metrics["tc_provider_requests"],
            "tc_provider_requests_total",
            labels,
        )
        == 1.0
    )


def test_redis_collector_handles_redis_read_errors_without_raising(monkeypatch):
    mod = importlib.import_module("pipeline.metrics")
    if not metrics_redis_backend.REDIS_OPERATION_ERRORS:
        pytest.skip("redis package is optional in local test environments")

    redis_error = metrics_redis_backend.REDIS_OPERATION_ERRORS[0]

    class _FailingRedis:
        def scan_iter(self, match=None):
            _ = match
            raise redis_error("scan failed")

    monkeypatch.setattr(metrics_redis_backend, "_REDIS_INIT", True)
    monkeypatch.setattr(metrics_redis_backend, "_REDIS_BACKEND_UP", 1.0)
    monkeypatch.setattr(metrics_redis_backend, "_REDIS_CLIENT", _FailingRedis())

    collector = mod.RedisProviderMetricsCollector()
    metrics = list(collector.collect())

    names = [m.name for m in metrics]
    assert "tc_provider_metrics_backend_up" in names
    assert metrics_redis_backend._REDIS_BACKEND_UP == 0.0


def test_redis_collector_skips_malformed_keys_and_degrades_bad_values(monkeypatch):
    mod = importlib.import_module("pipeline.metrics")

    class _MalformedRedis:
        def scan_iter(self, match=None):
            _ = match
            yield "tc:provider:req_total:missing_parts"
            yield "tc:provider:ttft_ms:bucket:http:summarize_text:gemma:ok"

        def get(self, key):
            _ = key
            return "not-a-number"

        def hgetall(self, key):
            if ":bucket:" in key:
                return {"100.0": "bad-value"}
            return {"count": "bad-count", "sum": "bad-sum"}

    monkeypatch.setattr(metrics_redis_backend, "_REDIS_INIT", True)
    monkeypatch.setattr(metrics_redis_backend, "_REDIS_BACKEND_UP", 1.0)
    monkeypatch.setattr(metrics_redis_backend, "_REDIS_CLIENT", _MalformedRedis())

    collector = mod.RedisProviderMetricsCollector()
    metrics = {m.name: m for m in collector.collect()}

    assert "tc_provider_requests" in metrics
    assert metrics_redis_backend._REDIS_BACKEND_UP == 0.0


def test_redis_collector_degrades_for_malformed_label_keys(monkeypatch):
    class _MalformedLabelsRedis:
        def scan_iter(self, match=None):
            if match == "tc:provider:req_total:*":
                yield "tc:provider:req_total:missing_parts"

        def get(self, key):
            _ = key
            return "5"

        def hgetall(self, key):
            _ = key
            return {}

    monkeypatch.setattr(metrics_redis_backend, "_REDIS_INIT", True)
    monkeypatch.setattr(metrics_redis_backend, "_REDIS_BACKEND_UP", 1.0)
    monkeypatch.setattr(
        metrics_redis_backend,
        "_REDIS_CLIENT",
        _MalformedLabelsRedis(),
    )

    list(metrics.RedisProviderMetricsCollector().collect())

    assert metrics_redis_backend._REDIS_BACKEND_UP == 0.0

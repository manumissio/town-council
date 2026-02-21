import importlib


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

    def hgetall(self, key):
        return self.hashes.get(key, {})


def test_redis_collector_exports_provider_series(monkeypatch):
    mod = importlib.import_module("pipeline.metrics")

    monkeypatch.setattr(mod, "_REDIS_INIT", True)
    monkeypatch.setattr(mod, "_REDIS_BACKEND_UP", 1.0)
    monkeypatch.setattr(mod, "_REDIS_CLIENT", _FakeRedis())

    collector = mod.RedisProviderMetricsCollector()
    metrics = {m.name: m for m in collector.collect()}

    labels = {
        "provider": "http",
        "operation": "summarize_text",
        "model": "gemma-3-270m-custom",
        "outcome": "ok",
    }
    assert "tc_provider_requests_total" in metrics
    assert _sample_value(metrics["tc_provider_requests_total"], "tc_provider_requests_total", labels) == 5.0
    assert _sample_value(metrics["tc_provider_prompt_tokens_total"], "tc_provider_prompt_tokens_total", labels) == 120.0
    assert _sample_value(metrics["tc_provider_completion_tokens_total"], "tc_provider_completion_tokens_total", labels) == 80.0
    assert _sample_value(
        metrics["tc_provider_ttft_ms"],
        "tc_provider_ttft_ms_count",
        labels,
    ) == 3.0
    assert _sample_value(
        metrics["tc_provider_tokens_per_sec"],
        "tc_provider_tokens_per_sec_count",
        labels,
    ) == 3.0

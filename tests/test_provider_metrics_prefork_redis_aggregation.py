import inspect
import logging
import os
import subprocess
import sys
from pathlib import Path

import pytest

from pipeline import (
    metrics,
    metrics_provider_recorders,
    metrics_redis_backend,
    metrics_task_recorders,
)


ROOT = Path(__file__).resolve().parents[1]


def _metric_sample_value(metric, sample_name, expected_labels):
    for collected_metric in metric.collect():
        for sample in collected_metric.samples:
            if sample.name == sample_name and all(
                sample.labels.get(label_name) == label_value
                for label_name, label_value in expected_labels.items()
            ):
                return float(sample.value)
    return 0.0


class FakeRedis:
    def __init__(self):
        self.kv = {}
        self.hashes = {}

    def ping(self):
        return True

    def incrby(self, key, amount):
        self.kv[key] = int(self.kv.get(key, 0)) + int(amount)

    def hincrby(self, key, field, amount):
        bucket = self.hashes.setdefault(key, {})
        bucket[field] = int(bucket.get(field, 0)) + int(amount)

    def hincrbyfloat(self, key, field, amount):
        bucket = self.hashes.setdefault(key, {})
        bucket[field] = float(bucket.get(field, 0.0)) + float(amount)


def test_record_provider_metrics_mirror_to_redis(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr(metrics_redis_backend, "_redis_client", lambda: fake)

    metrics.record_provider_request("http", "summarize_text", "gemma", "ok", 111.0)
    metrics.record_provider_timeout("http", "summarize_text", "gemma")
    metrics.record_provider_retry("http", "summarize_text", "gemma")
    metrics.record_provider_token_counts("http", "summarize_text", "gemma", "ok", 120, 35)
    metrics.record_provider_ttft("http", "summarize_text", "gemma", "ok", 230.0)
    metrics.record_provider_tokens_per_sec("http", "summarize_text", "gemma", "ok", 17.5)

    label4 = metrics._provider_labels_key("http", "summarize_text", "gemma", "ok")
    label3 = metrics._provider_base_labels_key("http", "summarize_text", "gemma")

    assert fake.kv[f"tc:provider:req_total:{label4}"] == 1
    assert fake.kv[f"tc:provider:timeouts_total:{label3}"] == 1
    assert fake.kv[f"tc:provider:retries_total:{label3}"] == 1
    assert fake.kv[f"tc:provider:prompt_tokens_total:{label4}"] == 120
    assert fake.kv[f"tc:provider:completion_tokens_total:{label4}"] == 35

    ttft_bucket_key = f"tc:provider:ttft_ms:bucket:{label4}"
    tps_bucket_key = f"tc:provider:tps:bucket:{label4}"
    assert fake.hashes[ttft_bucket_key]["250.0"] == 1
    assert fake.hashes[tps_bucket_key]["20.0"] == 1


def test_provider_label_keys_round_trip_special_characters():
    labels_key = metrics._provider_labels_key("http", "summarize:text", "gemma/custom", "ok value")
    assert labels_key == "http:summarize%3Atext:gemma%2Fcustom:ok%20value"

    labels = metrics._provider_base_labels_key("http", "summarize:text", "gemma/custom")
    assert labels == "http:summarize%3Atext:gemma%2Fcustom"


def test_provider_recorder_exports_prometheus_samples(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr(metrics_redis_backend, "_redis_client", lambda: fake)
    labels = {
        "provider": "http",
        "operation": "summarize_text",
        "model": "gemma",
        "outcome": "ok",
    }
    requests_before = _metric_sample_value(
        metrics.PROVIDER_REQUESTS_TOTAL,
        "tc_provider_requests_total",
        labels,
    )
    duration_count_before = _metric_sample_value(
        metrics.PROVIDER_REQUEST_DURATION_MS,
        "tc_provider_request_duration_ms_count",
        labels,
    )

    metrics.record_provider_request("http", "summarize_text", "gemma", "ok", 42.0)

    assert (
        _metric_sample_value(
            metrics.PROVIDER_REQUESTS_TOTAL,
            "tc_provider_requests_total",
            labels,
        )
        == requests_before + 1
    )
    assert (
        _metric_sample_value(
            metrics.PROVIDER_REQUEST_DURATION_MS,
            "tc_provider_request_duration_ms_count",
            labels,
        )
        == duration_count_before + 1
    )


def test_metrics_import_does_not_initialize_redis():
    import_probe = (
        "from pipeline import metrics_redis_backend\n"
        "assert metrics_redis_backend._REDIS_INIT is False\n"
        "from pipeline import metrics\n"
        "assert metrics_redis_backend._REDIS_INIT is False\n"
    )
    probe_environment = os.environ.copy()
    probe_environment["PYTHONPATH"] = "."

    subprocess.run(
        [sys.executable, "-c", import_probe],
        cwd=ROOT,
        env=probe_environment,
        check=True,
    )


def test_metrics_redis_backend_is_single_state_owner():
    facade_only_names = (
        "_REDIS_CLIENT",
        "_REDIS_INIT",
        "_REDIS_WARNED",
        "_REDIS_BACKEND_UP",
        "_sync_redis_backend_from_facade",
        "_sync_redis_facade_from_backend",
        "_redis_client",
        "_get_redis_backend_up",
        "_set_redis_backend_up",
        "_redis_incr",
        "_redis_hincrby",
        "_redis_hincrbyfloat",
    )

    assert all(not hasattr(metrics, facade_name) for facade_name in facade_only_names)
    assert (
        metrics.RedisProviderMetricsCollector
        is metrics_redis_backend.RedisProviderMetricsCollector
    )
    assert not hasattr(metrics_provider_recorders, "_facade_metric")
    assert not hasattr(metrics_task_recorders, "_facade_metric")
    for recorder_name in (
        "record_provider_request",
        "record_provider_ttft",
        "record_provider_tokens_per_sec",
        "record_provider_token_counts",
        "record_provider_timeout",
        "record_provider_retry",
    ):
        assert not {
            "redis_incr",
            "redis_hincrby",
            "redis_hincrbyfloat",
        }.intersection(
            inspect.signature(
                getattr(metrics_provider_recorders, recorder_name)
            ).parameters
        )


def test_redis_unavailable_warns_once_and_stays_degraded(monkeypatch, caplog):
    monkeypatch.setattr(metrics_redis_backend, "redis", None)
    monkeypatch.setattr(metrics_redis_backend, "_REDIS_CLIENT", None)
    monkeypatch.setattr(metrics_redis_backend, "_REDIS_INIT", False)
    monkeypatch.setattr(metrics_redis_backend, "_REDIS_WARNED", False)
    monkeypatch.setattr(metrics_redis_backend, "_REDIS_BACKEND_UP", 1.0)
    caplog.set_level(logging.WARNING, logger=metrics_redis_backend.__name__)

    assert metrics_redis_backend._redis_client() is None
    assert metrics_redis_backend._redis_client() is None
    warnings = [
        record
        for record in caplog.records
        if "metrics.redis_unavailable" in record.getMessage()
    ]

    assert len(warnings) == 1
    assert metrics_redis_backend._REDIS_INIT is True
    assert metrics_redis_backend._REDIS_BACKEND_UP == 0.0


class WriteFailingRedis:
    def incrby(self, key, amount):
        raise RuntimeError(f"incrby failed for {key}:{amount}")

    def hincrby(self, key, field, amount):
        raise RuntimeError(f"hincrby failed for {key}:{field}:{amount}")

    def hincrbyfloat(self, key, field, amount):
        raise RuntimeError(f"hincrbyfloat failed for {key}:{field}:{amount}")


@pytest.mark.parametrize(
    ("write_operation", "operation_args"),
    (
        (metrics_redis_backend._redis_incr, ("counter", 2)),
        (metrics_redis_backend._redis_hincrby, ("hash", "field", 2)),
        (metrics_redis_backend._redis_hincrbyfloat, ("hash", "field", 2.5)),
    ),
)
def test_redis_write_failures_mark_backend_degraded(
    monkeypatch,
    write_operation,
    operation_args,
):
    monkeypatch.setattr(
        metrics_redis_backend,
        "_redis_client",
        lambda: WriteFailingRedis(),
    )
    monkeypatch.setattr(metrics_redis_backend, "_REDIS_BACKEND_UP", 1.0)

    write_operation(*operation_args)

    assert metrics_redis_backend._REDIS_BACKEND_UP == 0.0

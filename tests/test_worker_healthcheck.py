import importlib.util
import os
import sys
from pathlib import Path


spec = importlib.util.spec_from_file_location(
    "worker_healthcheck", Path("scripts/worker_healthcheck.py")
)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def test_socket_target_from_url_parses_host_and_port():
    host, port = mod._socket_target_from_url("redis://:secret@redis:6379/0")
    assert host == "redis"
    assert port == 6379


def test_worker_healthcheck_main_returns_zero_when_all_probes_pass(monkeypatch):
    monkeypatch.setenv("TC_WORKER_METRICS_PORT", "8001")
    monkeypatch.setenv("CELERY_BROKER_URL", "redis://:secret@redis:6379/0")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@postgres:5432/town_council_db")
    monkeypatch.setenv("LOCAL_AI_BACKEND", "http")
    monkeypatch.setenv("LOCAL_AI_HTTP_BASE_URL", "http://inference:11434")
    monkeypatch.setenv("LOCAL_AI_HTTP_MODEL", "gemma-3-270m-custom")
    monkeypatch.setattr(mod, "_probe_tcp", lambda host, port, label: None)
    monkeypatch.setattr(mod, "_probe_http_model", lambda base_url, model_name: None)

    assert mod.main() == 0


def test_worker_healthcheck_main_returns_one_with_compact_failures(monkeypatch, capsys):
    monkeypatch.setenv("TC_WORKER_METRICS_PORT", "8001")
    monkeypatch.setenv("CELERY_BROKER_URL", "redis://:secret@redis:6379/0")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@postgres:5432/town_council_db")
    monkeypatch.setenv("LOCAL_AI_BACKEND", "http")
    monkeypatch.setenv("LOCAL_AI_HTTP_BASE_URL", "http://inference:11434")
    monkeypatch.setenv("LOCAL_AI_HTTP_MODEL", "gemma-3-270m-custom")

    def fake_probe(host, port, label):
        return f"{label} probe failed: boom" if label != "postgres" else None

    monkeypatch.setattr(mod, "_probe_tcp", fake_probe)
    monkeypatch.setattr(mod, "_probe_http_model", lambda base_url, model_name: None)

    assert mod.main() == 1
    stderr = capsys.readouterr().err
    assert "worker metrics probe failed: boom" in stderr
    assert "redis broker probe failed: boom" in stderr


def test_worker_healthcheck_reports_missing_inference_model(monkeypatch, capsys):
    monkeypatch.setenv("TC_WORKER_METRICS_PORT", "8001")
    monkeypatch.setenv("CELERY_BROKER_URL", "redis://:secret@redis:6379/0")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@postgres:5432/town_council_db")
    monkeypatch.setenv("LOCAL_AI_BACKEND", "http")
    monkeypatch.setenv("LOCAL_AI_HTTP_BASE_URL", "http://inference:11434")
    monkeypatch.setenv("LOCAL_AI_HTTP_MODEL", "gemma-3-270m-custom")
    monkeypatch.setattr(mod, "_probe_tcp", lambda host, port, label: None)
    monkeypatch.setattr(
        mod,
        "_probe_http_model",
        lambda base_url, model_name: f"inference model probe failed: model '{model_name}' is missing",
    )

    assert mod.main() == 1
    stderr = capsys.readouterr().err
    assert "inference model probe failed: model 'gemma-3-270m-custom' is missing" in stderr

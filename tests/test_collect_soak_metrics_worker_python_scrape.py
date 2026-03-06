import importlib.util
from pathlib import Path
import subprocess


spec = importlib.util.spec_from_file_location("collect_soak_metrics", Path("scripts/collect_soak_metrics.py"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_worker_scrape_command_uses_python(monkeypatch):
    seen = {}

    def _fake_check_output(cmd, **_kwargs):
        seen["cmd"] = cmd
        return "# HELP x y\n"

    monkeypatch.setattr(subprocess, "check_output", _fake_check_output)
    raw, err = mod._fetch_worker_metrics_via_docker()
    assert err is None
    assert "# HELP" in raw
    assert seen["cmd"][:6] == ["docker", "compose", "exec", "-T", "worker", "python"]
    assert "-c" in seen["cmd"]


def test_worker_scrape_falls_back_to_registry_strategy(monkeypatch):
    calls = {"n": 0}

    def _fake_exec(script: str):
        calls["n"] += 1
        if "localhost:8001/metrics" in script:
            raise RuntimeError("http probe failed")
        assert "RedisProviderMetricsCollector" in script
        return "tc_provider_requests_total 1\n"

    monkeypatch.setattr(mod, "_docker_exec_python", _fake_exec)
    monkeypatch.setattr(mod.time, "sleep", lambda *_args, **_kwargs: None)
    raw, err = mod._fetch_worker_metrics_via_docker()

    assert "tc_provider_requests_total" in raw
    assert err is None
    assert calls["n"] >= 2


def test_worker_scrape_falls_back_when_http_has_no_provider_series(monkeypatch):
    calls = {"n": 0}

    def _fake_exec(script: str):
        calls["n"] += 1
        if "localhost:8001/metrics" in script:
            return "# HELP python_info Python platform information\npython_info 1\n"
        assert "RedisProviderMetricsCollector" in script
        return "tc_provider_requests_total{provider=\"http\"} 2\n"

    monkeypatch.setattr(mod, "_docker_exec_python", _fake_exec)
    monkeypatch.setattr(mod.time, "sleep", lambda *_args, **_kwargs: None)
    raw, err = mod._fetch_worker_metrics_via_docker()

    assert "tc_provider_requests_total" in raw
    assert err is None
    assert calls["n"] >= 2

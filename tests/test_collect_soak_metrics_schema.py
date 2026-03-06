import importlib.util
import subprocess
from pathlib import Path


spec = importlib.util.spec_from_file_location("collect_soak_metrics", Path("scripts/collect_soak_metrics.py"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_parse_metrics_reads_labeled_rows():
    raw = '\n'.join([
        'tc_provider_requests_total{provider="http",operation="summarize_text",model="m",outcome="ok"} 10',
        'tc_provider_timeouts_total{provider="http",operation="summarize_text",model="m"} 1',
    ])
    rows = mod._parse_metrics(raw)
    assert len(rows) == 2
    assert rows[0]["name"] == "tc_provider_requests_total"
    assert rows[0]["labels"]["provider"] == "http"


def test_hist_quantile_handles_missing_data():
    assert mod._hist_quantile([], "tc_provider_ttft_ms", {}, 0.95) is None


def test_fetch_worker_metrics_returns_error_string_on_failure(monkeypatch):
    def _boom(*_args, **_kwargs):
        raise subprocess.CalledProcessError(1, "docker compose exec")

    monkeypatch.setattr(subprocess, "check_output", _boom)
    monkeypatch.setattr(mod.time, "sleep", lambda *_args, **_kwargs: None)
    raw, err = mod._fetch_worker_metrics_via_docker()
    assert raw == ""
    assert err is not None
    assert "worker_http" in err
    assert "worker_registry" in err


def test_fetch_worker_metrics_uses_python_probe(monkeypatch):
    captured = {}

    def _ok(cmd, **_kwargs):
        captured["cmd"] = cmd
        return "metric 1\n"

    monkeypatch.setattr(subprocess, "check_output", _ok)
    raw, err = mod._fetch_worker_metrics_via_docker()
    assert raw == "metric 1\n"
    assert err is None
    assert captured["cmd"][:6] == ["docker", "compose", "exec", "-T", "worker", "python"]


def test_fetch_worker_metrics_retries_before_failure(monkeypatch):
    calls = {"n": 0}

    def _boom(*_args, **_kwargs):
        calls["n"] += 1
        raise subprocess.CalledProcessError(1, "docker compose exec")

    monkeypatch.setattr(subprocess, "check_output", _boom)
    monkeypatch.setattr(mod.time, "sleep", lambda *_args, **_kwargs: None)
    raw, err = mod._fetch_worker_metrics_via_docker()
    assert raw == ""
    assert err is not None
    # 2 strategies x 2 attempts each.
    assert calls["n"] == 4


def test_provider_metrics_state_prefers_scrape_failure():
    present, reason = mod._provider_metrics_state(
        [{"name": "tc_provider_requests_total", "labels": {}, "value": 1.0}],
        "timeout",
    )
    assert not present
    assert reason == "worker_scrape_failed"

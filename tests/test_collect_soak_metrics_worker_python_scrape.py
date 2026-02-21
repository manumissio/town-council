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

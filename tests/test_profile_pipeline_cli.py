import importlib.util
import json
from pathlib import Path


spec = importlib.util.spec_from_file_location("profile_pipeline", Path("scripts/profile_pipeline.py"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_profile_pipeline_requires_manifest_for_baseline(tmp_path: Path):
    try:
        mod.main(["--mode", "baseline", "--output-dir", str(tmp_path)])
    except SystemExit as exc:
        assert "--manifest is required for baseline mode" in str(exc)
    else:
        raise AssertionError("expected SystemExit")


def test_profile_pipeline_writes_manifest_and_result(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(mod, "_select_triage_catalog_ids", lambda limit, city: [11, 12])
    monkeypatch.setattr(mod, "_provider_counters_before_run", lambda: {"provider_requests_total": 1.0, "provider_timeouts_total": 0.0, "provider_retries_total": 0.0})
    commands = []

    def _fake_run(command, **kwargs):
        commands.append((command, kwargs))
        return type("Completed", (), {"returncode": 0})()

    monkeypatch.setattr(mod.subprocess, "run", _fake_run)
    exit_code = mod.main(["--mode", "triage", "--output-dir", str(tmp_path), "--skip-batch"])

    run_dirs = list(tmp_path.iterdir())
    assert exit_code == 0
    assert len(run_dirs) == 1
    manifest = json.loads((run_dirs[0] / "run_manifest.json").read_text(encoding="utf-8"))
    result = json.loads((run_dirs[0] / "result.json").read_text(encoding="utf-8"))
    assert manifest["catalog_ids"] == [11, 12]
    assert result["status"] == "completed"
    assert any("collect_soak_metrics.py" in " ".join(cmd) for cmd, _ in commands)

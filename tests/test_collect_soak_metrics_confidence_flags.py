import importlib.util
import json
from pathlib import Path


spec = importlib.util.spec_from_file_location("collect_soak_metrics", Path("scripts/collect_soak_metrics.py"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_provider_metrics_state_no_provider_series():
    present, reason = mod._provider_metrics_state(
        [{"name": "tc_other_metric", "labels": {}, "value": 1.0}],
        None,
    )
    assert not present
    assert reason == "no_provider_series"


def test_day_summary_marks_provider_metrics_reason(monkeypatch, tmp_path):
    worker_metrics = "\n".join(
        [
            'tc_provider_requests_total{provider="http",operation="summarize_text",model="m",outcome="ok"} 2',
            'tc_provider_timeouts_total{provider="http",operation="summarize_text",model="m"} 0',
        ]
    )
    monkeypatch.setattr(mod, "_fetch_worker_metrics_via_docker", lambda: (worker_metrics, None))
    monkeypatch.setattr(mod, "_fetch_text", lambda *_args, **_kwargs: "up 1\n")

    run_id = "soak_reason_flags"
    monkeypatch.setattr(
        "sys.argv",
        [
            "collect_soak_metrics.py",
            "--run-id",
            run_id,
            "--output-dir",
            str(tmp_path),
            "--api-url",
            "http://localhost:8000",
        ],
    )
    assert mod.main() == 0
    day_summary = json.loads((tmp_path / run_id / "day_summary.json").read_text(encoding="utf-8"))
    assert day_summary["provider_metrics_present"] is True
    assert day_summary["provider_metrics_reason"] == "ok"

import importlib.util
import json
from pathlib import Path


spec = importlib.util.spec_from_file_location("collect_soak_metrics", Path("scripts/collect_soak_metrics.py"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_day_summary_populates_ttft_tps_when_provider_metrics_exist(monkeypatch, tmp_path):
    worker_metrics = "\n".join(
        [
            'tc_provider_requests_total{provider="http",operation="summarize_text",model="gemma-3-270m-custom",outcome="ok"} 4',
            'tc_provider_timeouts_total{provider="http",operation="summarize_text",model="gemma-3-270m-custom"} 0',
            'tc_provider_retries_total{provider="http",operation="summarize_text",model="gemma-3-270m-custom"} 0',
            'tc_provider_prompt_tokens_total{provider="http",operation="summarize_text",model="gemma-3-270m-custom",outcome="ok"} 300',
            'tc_provider_completion_tokens_total{provider="http",operation="summarize_text",model="gemma-3-270m-custom",outcome="ok"} 120',
            'tc_provider_ttft_ms_bucket{provider="http",operation="summarize_text",model="gemma-3-270m-custom",outcome="ok",le="100.0"} 1',
            'tc_provider_ttft_ms_bucket{provider="http",operation="summarize_text",model="gemma-3-270m-custom",outcome="ok",le="250.0"} 4',
            'tc_provider_ttft_ms_bucket{provider="http",operation="summarize_text",model="gemma-3-270m-custom",outcome="ok",le="+Inf"} 4',
            'tc_provider_tokens_per_sec_bucket{provider="http",operation="summarize_text",model="gemma-3-270m-custom",outcome="ok",le="10.0"} 1',
            'tc_provider_tokens_per_sec_bucket{provider="http",operation="summarize_text",model="gemma-3-270m-custom",outcome="ok",le="20.0"} 4',
            'tc_provider_tokens_per_sec_bucket{provider="http",operation="summarize_text",model="gemma-3-270m-custom",outcome="ok",le="+Inf"} 4',
        ]
    )

    monkeypatch.setattr(mod, "_fetch_worker_metrics_via_docker", lambda: (worker_metrics, None))

    def _fake_fetch(url: str, timeout: int = 10) -> str:
        if url.endswith("/metrics"):
            return "up 1\n"
        return '{"ok":true}'

    monkeypatch.setattr(mod, "_fetch_text", _fake_fetch)

    run_id = "soak_test_ttft_tps"
    run_dir = tmp_path / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "run_manifest.json").write_text(
        json.dumps(
            {
                "catalog_ids": [609, 933],
                "catalog_count": 2,
                "profile": {"LOCAL_AI_BACKEND": "http", "LOCAL_AI_HTTP_PROFILE": "conservative"},
                "provider_counters_before_run": {
                    "provider_requests_total": 1.0,
                    "provider_timeouts_total": 0.0,
                    "provider_retries_total": 0.0,
                },
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "tasks.jsonl").write_text(
        "\n".join(
            [
                json.dumps({"catalog_id": 609, "phase": "segment", "duration_s": 10.0}),
                json.dumps({"catalog_id": 933, "phase": "summarize", "duration_s": 7.0}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
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
    assert day_summary["provider_requests_total"] == 4.0
    assert day_summary["ttft_median_ms"] is not None
    assert day_summary["ttft_p95_ms"] is not None
    assert day_summary["tokens_per_sec_median"] is not None
    assert day_summary["prompt_tokens_total"] == 300.0
    assert day_summary["completion_tokens_total"] == 120.0
    assert day_summary["provider_requests_delta_run"] == 3.0
    assert day_summary["provider_timeout_rate_run"] == 0.0
    assert day_summary["segment_max_s"] == 10.0
    assert day_summary["summary_max_s"] == 7.0

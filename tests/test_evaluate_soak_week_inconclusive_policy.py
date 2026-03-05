import json
import subprocess
from pathlib import Path


def _write_day(root: Path, run_id: str, ts: int, **overrides) -> None:
    run_dir = root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "run_id": run_id,
        "timestamp_epoch_s": ts,
        "status": "complete",
        "gating_failures": 0,
        "extract_failures": 0,
        "phases_total": 6,
        "segment_failures": 0,
        "summarize_failures": 0,
        "segment_p95_s": 100.0,
        "summary_p95_s": 40.0,
        "phase_duration_p95_s": 120.0,
        "search_p95_ms": 25.0,
        "provider_requests_total": 0.0,
        "provider_timeouts_total": 0.0,
        "provider_retries_total": 0.0,
        "ttft_p95_ms": None,
        "tokens_per_sec_median": None,
        "metrics_sources": {"worker_metrics_available": True, "api_metrics_available": True},
    }
    payload.update(overrides)
    (run_dir / "day_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_timeout_rate_gate_is_inconclusive_when_no_provider_request_deltas(tmp_path):
    root = tmp_path / "soak"
    for i in range(7):
        _write_day(root, f"soak_day_{i}", 1_700_000_000 + i, provider_requests_total=0.0)

    subprocess.run(
        [
            ".venv/bin/python",
            "scripts/evaluate_soak_week.py",
            "--input-dir",
            str(root),
            "--window-days",
            "7",
        ],
        check=True,
    )

    out = json.loads((root / "soak_eval_7d.json").read_text(encoding="utf-8"))
    assert out["gate_statuses"]["provider_timeout_rate_lt_1pct"] == "INCONCLUSIVE"
    assert out["gate_reasons"]["provider_timeout_rate_lt_1pct"] == "missing_provider_request_deltas"
    assert out["gates"]["provider_timeout_rate_lt_1pct"] is False
    assert out["overall_status"] == "INCONCLUSIVE"
    assert out["overall_pass"] is False

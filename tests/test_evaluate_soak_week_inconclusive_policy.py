import json
import subprocess
from pathlib import Path


def _write_day(
    root: Path,
    run_id: str,
    ts: int,
    *,
    baseline_valid: bool = True,
    run_manifest_text: str | None = None,
    day_summary_baseline_valid: bool | None = None,
    **overrides,
) -> None:
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
        "provider_requests_delta_run": None,
        "provider_timeouts_delta_run": None,
        "provider_retries_delta_run": None,
        "ttft_p95_ms": None,
        "tokens_per_sec_median": None,
        "metrics_sources": {"worker_metrics_available": True, "api_metrics_available": True},
    }
    payload.update(overrides)
    if day_summary_baseline_valid is not None:
        payload["baseline_valid"] = day_summary_baseline_valid
    (run_dir / "day_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    if run_manifest_text is None:
        run_manifest_text = json.dumps({"baseline_valid": baseline_valid})
    if run_manifest_text:
        (run_dir / "run_manifest.json").write_text(run_manifest_text, encoding="utf-8")


def test_timeout_rate_gate_is_inconclusive_when_no_provider_request_deltas(tmp_path):
    root = tmp_path / "soak"
    for i in range(7):
        _write_day(
            root,
            f"soak_day_{i}",
            1_700_000_000 + i,
            provider_requests_total=100.0 + i,
            provider_requests_delta_run=None,
            provider_timeouts_delta_run=None,
            provider_retries_delta_run=None,
        )

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
    assert out["gate_reasons"]["provider_timeout_rate_lt_1pct"] == "missing_run_local_provider_deltas"
    assert out["gates"]["provider_timeout_rate_lt_1pct"] is False
    assert out["overall_status"] == "INCONCLUSIVE"
    assert out["overall_pass"] is False
    assert out["baseline_valid"] is False
    assert "baseline_contaminated" in out["evidence_quality_reasons"]


def test_timeout_rate_gate_prefers_run_local_deltas_over_cumulative_totals(tmp_path):
    root = tmp_path / "soak"
    for i in range(7):
        _write_day(
            root,
            f"soak_day_{i}",
            1_700_001_000 + i,
            provider_requests_total=1000.0 + (50.0 * i),
            provider_timeouts_total=300.0 + (5.0 * i),
            provider_retries_total=150.0 + (2.0 * i),
            provider_requests_delta_run=50.0,
            provider_timeouts_delta_run=0.0,
            provider_retries_delta_run=0.0,
        )

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
    assert out["gate_statuses"]["provider_timeout_rate_lt_1pct"] == "PASS"
    assert out["baseline_valid"] is True
    assert out["per_day"][0]["promotion_evidence_source"] == "run_delta"


def test_diagnostic_days_do_not_count_as_promotion_grade_baseline_artifacts(tmp_path):
    root = tmp_path / "soak"
    for i in range(7):
        _write_day(
            root,
            f"diagnostic_day_{i}",
            1_700_002_000 + i,
            baseline_valid=False,
            provider_requests_delta_run=50.0,
            provider_timeouts_delta_run=0.0,
            provider_retries_delta_run=0.0,
        )

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
    assert out["baseline_artifact_days"] == 0
    assert out["baseline_valid"] is False
    assert out["per_day"][0]["baseline_valid"] is False
    assert out["gate_statuses"]["provider_timeout_rate_lt_1pct"] == "INCONCLUSIVE"
    assert out["gate_reasons"]["provider_timeout_rate_lt_1pct"] == "non_baseline_artifact_days"
    assert out["overall_status"] == "INCONCLUSIVE"
    assert out["overall_pass"] is False
    assert "baseline_contaminated" in out["evidence_quality_reasons"]


def test_missing_run_manifest_fails_closed_despite_stale_day_summary_flag(tmp_path):
    root = tmp_path / "soak"
    for i in range(7):
        _write_day(
            root,
            f"missing_manifest_day_{i}",
            1_700_003_000 + i,
            run_manifest_text="",
            baseline_valid=True,
            day_summary_baseline_valid=True,
            provider_requests_delta_run=50.0,
            provider_timeouts_delta_run=0.0,
            provider_retries_delta_run=0.0,
        )

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
    assert out["baseline_artifact_days"] == 0
    assert out["baseline_valid"] is False
    assert out["per_day"][0]["baseline_valid"] is False


def test_malformed_run_manifest_fails_closed(tmp_path):
    root = tmp_path / "soak"
    for i in range(7):
        _write_day(
            root,
            f"malformed_manifest_day_{i}",
            1_700_004_000 + i,
            run_manifest_text="{not-json",
            provider_requests_delta_run=50.0,
            provider_timeouts_delta_run=0.0,
            provider_retries_delta_run=0.0,
        )

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
    assert out["baseline_artifact_days"] == 0
    assert out["baseline_valid"] is False
    assert out["per_day"][0]["baseline_valid"] is False

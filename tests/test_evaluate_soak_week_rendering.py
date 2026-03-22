import importlib.util
from pathlib import Path


spec = importlib.util.spec_from_file_location("evaluate_soak_week", Path("scripts/evaluate_soak_week.py"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_render_markdown_uses_output_object_consistently():
    out = {
        "window_days": 2,
        "overall_status": "FAIL",
        "overall_pass": False,
        "extract_warning_days": 1,
        "telemetry_confidence": "high",
        "degraded_telemetry_days": 0,
        "baseline_valid": True,
        "baseline_artifact_days": 2,
        "evaluated_runs": ["soak_day_1", "soak_day_2"],
        "gates": {"provider_timeout_rate_lt_1pct": False},
        "gate_statuses": {"provider_timeout_rate_lt_1pct": "FAIL"},
        "gate_reasons": {"provider_timeout_rate_lt_1pct": "timeout_rate_threshold_exceeded"},
        "evidence_quality_reasons": [],
        "per_day": [
            {
                "date": "2026-03-21",
                "run_id": "soak_day_1",
                "status": "complete",
                "telemetry_confidence": "high",
                "promotion_evidence_source": "run_delta",
                "extract_failures": 1,
                "gating_failures": 0,
                "provider_timeout_rate_delta": 0.22,
                "segment_p95_s": 10.0,
                "summary_p95_s": 5.0,
            }
        ],
        "notes": ["Run-local provider deltas are required."],
    }

    rendered = mod._render_markdown(out)

    assert "overall_status: FAIL" in rendered
    assert "baseline_artifact_days: 2/2" in rendered
    assert "evaluated_runs: soak_day_1, soak_day_2" in rendered
    assert "provider_timeout_rate_lt_1pct: FAIL" in rendered
    assert "timeout_rate_delta=0.22" in rendered

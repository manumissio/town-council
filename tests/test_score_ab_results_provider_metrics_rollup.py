import importlib.util
from pathlib import Path


spec = importlib.util.spec_from_file_location("score_ab_results", Path("scripts/score_ab_results.py"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_aggregate_arm_rolls_up_provider_metrics():
    rows = [
        {
            "section_compliance_pass": True,
            "fallback_used": False,
            "grounding_pass": True,
            "task_failed": False,
            "partial_coverage_disclosed": False,
            "summary_duration_s": 10.0,
            "segment_duration_s": 20.0,
            "ttft_ms": 1000.0,
            "tokens_per_sec": 20.0,
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
        },
        {
            "section_compliance_pass": True,
            "fallback_used": False,
            "grounding_pass": True,
            "task_failed": False,
            "partial_coverage_disclosed": False,
            "summary_duration_s": 12.0,
            "segment_duration_s": 24.0,
            "ttft_ms": 1500.0,
            "tokens_per_sec": 10.0,
            "prompt_tokens": 80,
            "completion_tokens": 40,
            "total_tokens": 120,
        },
    ]
    agg = mod.aggregate_arm(rows)
    assert agg["ttft_median_ms"] == 1250.0
    assert agg["ttft_p95_ms"] == 1500.0
    assert agg["ttft_n"] == 2
    assert agg["tokens_per_sec_median"] == 15.0
    assert agg["tokens_per_sec_n"] == 2
    assert agg["prompt_tokens_total"] == 180
    assert agg["completion_tokens_total"] == 90
    assert agg["total_tokens_total"] == 270


def test_compare_arms_includes_provider_metric_deltas_without_new_checks():
    control = {
        "n": 10,
        "section_compliance_rate": 0.7,
        "fallback_rate": 0.1,
        "grounding_rate": 0.95,
        "failure_rate": 0.02,
        "summary_p95_s": 10.0,
        "segment_p95_s": 20.0,
        "partial_disclosure_rate": 0.0,
        "ttft_median_ms": 1200.0,
        "ttft_p95_ms": 1600.0,
        "ttft_n": 10,
        "tokens_per_sec_median": 18.0,
        "tokens_per_sec_n": 10,
        "prompt_tokens_total": 1000,
        "completion_tokens_total": 800,
        "total_tokens_total": 1800,
    }
    treatment = {**control, "ttft_median_ms": 1000.0, "tokens_per_sec_median": 22.0}
    out = mod.compare_arms(control, treatment)
    assert "ttft_median_ms_delta" in out["deltas"]
    assert "tokens_per_sec_median_delta" in out["deltas"]
    # Gate keys remain unchanged in this iteration (metrics are non-gating).
    assert set(out["checks"].keys()) == {
        "section_compliance",
        "fallback",
        "grounding",
        "summary_p95",
        "segment_p95",
        "failure_rate",
    }

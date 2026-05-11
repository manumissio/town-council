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


def test_aggregate_arm_empty_payload_preserves_zero_contract():
    assert mod.aggregate_arm([]) == {
        "n": 0,
        "section_compliance_rate": 0.0,
        "fallback_rate": 0.0,
        "grounding_rate": 0.0,
        "failure_rate": 0.0,
        "summary_p95_s": 0.0,
        "segment_p95_s": 0.0,
        "partial_disclosure_rate": 0.0,
        "ttft_median_ms": 0.0,
        "ttft_p95_ms": 0.0,
        "ttft_n": 0,
        "tokens_per_sec_median": 0.0,
        "tokens_per_sec_n": 0,
        "prompt_tokens_total": 0,
        "completion_tokens_total": 0,
        "total_tokens_total": 0,
    }


def test_aggregate_arm_tolerates_malformed_numeric_values():
    rows = [
        {
            "section_compliance_pass": "yes",
            "fallback_used": "no",
            "grounding_pass": "true",
            "task_failed": "",
            "partial_coverage_disclosed": "1",
            "summary_duration_s": "not-a-number",
            "segment_duration_s": None,
            "ttft_ms": "bad",
            "tokens_per_sec": "-1",
            "prompt_tokens": "bad",
            "completion_tokens": None,
            "total_tokens": "12.9",
        }
    ]

    agg = mod.aggregate_arm(rows)

    assert agg["section_compliance_rate"] == 1.0
    assert agg["fallback_rate"] == 0.0
    assert agg["grounding_rate"] == 1.0
    assert agg["failure_rate"] == 0.0
    assert agg["partial_disclosure_rate"] == 1.0
    assert agg["summary_p95_s"] == 0.0
    assert agg["segment_p95_s"] == 0.0
    assert agg["ttft_n"] == 0
    assert agg["tokens_per_sec_n"] == 0
    assert agg["prompt_tokens_total"] == 0
    assert agg["completion_tokens_total"] == 0
    assert agg["total_tokens_total"] == 12


def test_aggregate_arm_p95_uses_nearest_rank_contract():
    rows = [
        {"summary_duration_s": 1, "segment_duration_s": 10},
        {"summary_duration_s": 2, "segment_duration_s": 20},
        {"summary_duration_s": 3, "segment_duration_s": 30},
    ]

    agg = mod.aggregate_arm(rows)

    assert agg["summary_p95_s"] == 3.0
    assert agg["segment_p95_s"] == 30.0


def test_render_report_keeps_markdown_sections_and_metric_rows():
    control = mod.aggregate_arm([{"summary_duration_s": 1, "segment_duration_s": 2}])
    treatment = mod.aggregate_arm([{"summary_duration_s": 1, "segment_duration_s": 2}])
    comparison = mod.compare_arms(control, treatment)
    markdown = mod._render_report(
        control,
        treatment,
        comparison,
        ["run-a", "run-b"],
        {"A": {"run_id": "run-a", "model": "model-a"}, "B": {"run_id": "run-b", "model": "model-b"}},
    )

    assert "# A/B Report v1" in markdown
    assert "## Arm Identity" in markdown
    assert "## Arm Metrics" in markdown
    assert "## Gate Evaluation" in markdown
    assert "| Prompt tokens total | 0 | 0 |" in markdown
    assert "- overall: FAIL" in markdown


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


def test_arm_metadata_preserves_model_identity():
    rows = [
        {"arm": "A", "model": "gemma-3-270m-custom"},
        {"arm": "B", "model": "gemma4:e2b"},
    ]
    configs = [
        {
            "run_id": "A_run1",
            "arm": "A",
            "profile": {"LOCAL_AI_HTTP_PROFILE": "conservative", "LOCAL_AI_HTTP_MODEL": "gemma-3-270m-custom"},
        },
        {
            "run_id": "B_run1",
            "arm": "B",
            "profile": {"LOCAL_AI_HTTP_PROFILE": "conservative", "LOCAL_AI_HTTP_MODEL": "gemma4:e2b"},
        },
    ]

    metadata = mod._arm_metadata(rows, configs)

    assert metadata["A"]["model"] == "gemma-3-270m-custom"
    assert metadata["B"]["model"] == "gemma4:e2b"
    assert metadata["B"]["profile"]["LOCAL_AI_HTTP_PROFILE"] == "conservative"

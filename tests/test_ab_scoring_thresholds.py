import importlib.util
from pathlib import Path


spec = importlib.util.spec_from_file_location("score_ab_results", Path("scripts/score_ab_results.py"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_compare_arms_passes_when_all_balanced_gates_pass():
    control = {
        "n": 100,
        "section_compliance_rate": 0.70,
        "fallback_rate": 0.10,
        "grounding_rate": 0.95,
        "failure_rate": 0.02,
        "summary_p95_s": 10.0,
        "segment_p95_s": 20.0,
        "partial_disclosure_rate": 0.05,
    }
    treatment = {
        "n": 100,
        "section_compliance_rate": 0.76,  # +6pp
        "fallback_rate": 0.105,  # +0.5pp
        "grounding_rate": 0.945,  # -0.5pp
        "failure_rate": 0.025,  # +0.5pp
        "summary_p95_s": 12.0,  # +20%
        "segment_p95_s": 24.0,  # +20%
        "partial_disclosure_rate": 0.05,
    }

    out = mod.compare_arms(control, treatment)
    assert out["all_pass"] is True


def test_compare_arms_fails_when_section_improvement_too_small():
    control = {
        "n": 50,
        "section_compliance_rate": 0.70,
        "fallback_rate": 0.10,
        "grounding_rate": 0.95,
        "failure_rate": 0.02,
        "summary_p95_s": 10.0,
        "segment_p95_s": 20.0,
        "partial_disclosure_rate": 0.05,
    }
    treatment = {
        "n": 50,
        "section_compliance_rate": 0.74,  # +4pp (fails)
        "fallback_rate": 0.10,
        "grounding_rate": 0.95,
        "failure_rate": 0.02,
        "summary_p95_s": 10.0,
        "segment_p95_s": 20.0,
        "partial_disclosure_rate": 0.05,
    }

    out = mod.compare_arms(control, treatment)
    assert out["checks"]["section_compliance"] is False
    assert out["all_pass"] is False

import importlib.util
from pathlib import Path


spec = importlib.util.spec_from_file_location("collect_ab_results", Path("scripts/collect_ab_results.py"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_provider_metric_from_phase_row_uses_flat_field_first():
    row = {
        "ttft_ms": 123.4,
        "task_result": {
            "ttft_ms": 999.0,
        },
    }
    assert mod._provider_metric_from_phase_row(row, "ttft_ms") == 123.4


def test_provider_metric_from_phase_row_falls_back_to_nested_task_result():
    row = {
        "task_result": {
            "telemetry": {
                "tokens_per_sec": 18.5,
                "prompt_tokens": 120,
                "completion_tokens": 80,
                "prompt_eval_duration_ms": 2100.0,
                "eval_duration_ms": 4300.0,
            }
        }
    }
    assert mod._provider_metric_from_phase_row(row, "tokens_per_sec") == 18.5
    assert mod._provider_metric_from_phase_row(row, "prompt_tokens") == 120
    assert mod._provider_metric_from_phase_row(row, "completion_tokens") == 80
    assert mod._provider_metric_from_phase_row(row, "prompt_eval_duration_ms") == 2100.0
    assert mod._provider_metric_from_phase_row(row, "eval_duration_ms") == 4300.0

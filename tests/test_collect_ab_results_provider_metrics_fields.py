import importlib.util
import json
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


def test_numeric_conversion_helpers_return_none_for_malformed_values():
    assert mod._to_float("not-a-number") is None
    assert mod._to_float(None) is None
    assert mod._to_int("not-an-int") is None
    assert mod._to_int(None) is None


def test_load_run_config_returns_empty_dict_for_malformed_json(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "run_config.json").write_text("{not-json", encoding="utf-8")

    assert mod._load_run_config(run_dir) == {}


def test_load_run_config_returns_empty_dict_for_non_mapping_payload(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "run_config.json").write_text(json.dumps(["not", "a", "dict"]), encoding="utf-8")

    assert mod._load_run_config(run_dir) == {}

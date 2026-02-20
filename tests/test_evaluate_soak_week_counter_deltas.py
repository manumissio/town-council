import importlib.util
from pathlib import Path


spec = importlib.util.spec_from_file_location("evaluate_soak_week", Path("scripts/evaluate_soak_week.py"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_counter_delta_regular_and_reset():
    assert mod._counter_delta(12.0, 10.0) == 2.0
    # Counter reset: treat current as new baseline delta.
    assert mod._counter_delta(2.0, 10.0) == 2.0


def test_has_adverse_drift_higher_is_worse():
    assert mod._has_adverse_drift([10.0, 10.0, 14.0, 14.0], higher_is_worse=True, tolerance=0.2)
    assert not mod._has_adverse_drift([10.0, 10.0, 11.0, 11.0], higher_is_worse=True, tolerance=0.2)


def test_safe_int_defaults_zero():
    assert mod._safe_int("3") == 3
    assert mod._safe_int(None) == 0

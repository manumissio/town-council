import importlib.util
import sys
from pathlib import Path


spec = importlib.util.spec_from_file_location(
    "check_postgres_collation", Path("scripts/check_postgres_collation.py")
)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def test_collation_state_exit_zero_when_versions_match(monkeypatch, capsys):
    monkeypatch.setattr(
        mod,
        "_collation_state",
        lambda: {
            "database": "town_council_db",
            "expected_collversion": "2.36",
            "actual_collversion": "2.36",
            "matches": True,
        },
    )
    monkeypatch.setattr(sys, "argv", ["check_postgres_collation.py"])

    assert mod.main() == 0
    assert "matches=True" in capsys.readouterr().out


def test_collation_state_exit_three_when_versions_drift(monkeypatch, capsys):
    monkeypatch.setattr(
        mod,
        "_collation_state",
        lambda: {
            "database": "town_council_db",
            "expected_collversion": "2.41",
            "actual_collversion": "2.36",
            "matches": False,
        },
    )
    monkeypatch.setattr(sys, "argv", ["check_postgres_collation.py"])

    assert mod.main() == 3
    captured = capsys.readouterr()
    assert "matches=False" in captured.out
    assert "ALTER DATABASE town_council_db REFRESH COLLATION VERSION" in captured.err

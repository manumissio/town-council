import importlib.util
import json
import sys
from pathlib import Path


spec = importlib.util.spec_from_file_location("staged_hydrate_cities", Path("scripts/staged_hydrate_cities.py"))
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def test_staged_hydrate_cities_uses_default_city_order_and_emits_deltas(mocker, capsys):
    mocker.patch.object(
        mod,
        "_snapshot_dict",
        side_effect=[
            {"missing_summary_total": 5, "catalogs_with_summary": 0, "agenda_missing_summary_total": 5, "agenda_missing_summary_with_items": 0, "agenda_missing_summary_without_items": 5, "non_agenda_missing_summary_total": 0},
            {"missing_summary_total": 3, "catalogs_with_summary": 2, "agenda_missing_summary_total": 3, "agenda_missing_summary_with_items": 0, "agenda_missing_summary_without_items": 3, "non_agenda_missing_summary_total": 0},
            {"missing_summary_total": 2, "catalogs_with_summary": 1, "agenda_missing_summary_total": 0, "agenda_missing_summary_with_items": 0, "agenda_missing_summary_without_items": 0, "non_agenda_missing_summary_total": 2},
            {"missing_summary_total": 1, "catalogs_with_summary": 2, "agenda_missing_summary_total": 0, "agenda_missing_summary_with_items": 0, "agenda_missing_summary_without_items": 0, "non_agenda_missing_summary_total": 1},
            {"missing_summary_total": 10, "catalogs_with_summary": 0, "agenda_missing_summary_total": 9, "agenda_missing_summary_with_items": 0, "agenda_missing_summary_without_items": 9, "non_agenda_missing_summary_total": 1},
            {"missing_summary_total": 9, "catalogs_with_summary": 1, "agenda_missing_summary_total": 8, "agenda_missing_summary_with_items": 0, "agenda_missing_summary_without_items": 8, "non_agenda_missing_summary_total": 1},
            {"missing_summary_total": 20, "catalogs_with_summary": 0, "agenda_missing_summary_total": 20, "agenda_missing_summary_with_items": 0, "agenda_missing_summary_without_items": 20, "non_agenda_missing_summary_total": 0},
            {"missing_summary_total": 18, "catalogs_with_summary": 2, "agenda_missing_summary_total": 18, "agenda_missing_summary_with_items": 0, "agenda_missing_summary_without_items": 18, "non_agenda_missing_summary_total": 0},
            {"missing_summary_total": 100, "catalogs_with_summary": 0, "agenda_missing_summary_total": 100, "agenda_missing_summary_with_items": 0, "agenda_missing_summary_without_items": 100, "non_agenda_missing_summary_total": 0},
            {"missing_summary_total": 95, "catalogs_with_summary": 5, "agenda_missing_summary_total": 95, "agenda_missing_summary_with_items": 0, "agenda_missing_summary_without_items": 95, "non_agenda_missing_summary_total": 0},
        ],
    )
    segment_spy = mocker.patch.object(mod, "_run_segment_city", side_effect=lambda city: {"city": city, "catalog_count": 1, "complete": 1, "empty": 0, "failed": 0, "timed_out": 0})
    summary_spy = mocker.patch.object(mod, "run_summary_hydration_backfill", side_effect=lambda **kwargs: {"selected": 1, "complete": 1, "cached": 0, "stale": 0, "blocked_low_signal": 0, "blocked_ungrounded": 0, "not_generated_yet": 0, "error": 0, "other": 0})
    mocker.patch.object(sys, "argv", ["staged_hydrate_cities.py"])

    exit_code = mod.main()

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "city: hayward" in captured.out
    assert "city: san_mateo" in captured.out
    assert [call.args[0] for call in segment_spy.call_args_list] == ["hayward", "sunnyvale", "berkeley", "cupertino", "san_mateo"]
    assert [call.kwargs["city"] for call in summary_spy.call_args_list] == ["hayward", "sunnyvale", "berkeley", "cupertino", "san_mateo"]


def test_staged_hydrate_cities_json_mode(mocker, capsys):
    mocker.patch.object(mod, "_snapshot_dict", side_effect=[
        {"missing_summary_total": 1, "catalogs_with_summary": 0, "agenda_missing_summary_total": 1, "agenda_missing_summary_with_items": 0, "agenda_missing_summary_without_items": 1, "non_agenda_missing_summary_total": 0},
        {"missing_summary_total": 0, "catalogs_with_summary": 1, "agenda_missing_summary_total": 0, "agenda_missing_summary_with_items": 0, "agenda_missing_summary_without_items": 0, "non_agenda_missing_summary_total": 0},
    ])
    mocker.patch.object(mod, "_run_segment_city", return_value={"city": "berkeley", "catalog_count": 1, "complete": 1, "empty": 0, "failed": 0, "timed_out": 0})
    mocker.patch.object(mod, "run_summary_hydration_backfill", return_value={"selected": 1, "complete": 1, "cached": 0, "stale": 0, "blocked_low_signal": 0, "blocked_ungrounded": 0, "not_generated_yet": 0, "error": 0, "other": 0})
    mocker.patch.object(sys, "argv", ["staged_hydrate_cities.py", "--city", "berkeley", "--json"])

    exit_code = mod.main()

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["cities"][0]["city"] == "berkeley"

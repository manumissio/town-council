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
    segment_spy = mocker.patch.object(mod, "_run_segment_city", side_effect=lambda city, emit_progress=False: {"city": city, "catalog_count": 1, "complete": 1, "empty": 0, "failed": 0, "timed_out": 0})
    summary_spy = mocker.patch.object(mod, "run_summary_hydration_backfill", side_effect=lambda **kwargs: {"selected": 1, "complete": 1, "cached": 0, "stale": 0, "blocked_low_signal": 0, "blocked_ungrounded": 0, "not_generated_yet": 0, "error": 0, "other": 0})
    mocker.patch.object(sys, "argv", ["staged_hydrate_cities.py"])

    exit_code = mod.main()

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "[hayward] city_start" in captured.out
    assert "[hayward] before_snapshot" in captured.out
    assert "[hayward] summary_start" in captured.out
    assert "[hayward] city_finish" in captured.out
    assert "city: hayward" in captured.out
    assert "city: san_mateo" in captured.out
    assert [call.args[0] for call in segment_spy.call_args_list] == ["hayward", "sunnyvale", "berkeley", "cupertino", "san_mateo"]
    assert [call.kwargs["city"] for call in summary_spy.call_args_list] == ["hayward", "sunnyvale", "berkeley", "cupertino", "san_mateo"]
    assert all(call.kwargs["emit_progress"] is True for call in segment_spy.call_args_list)


def test_staged_hydrate_cities_json_mode(mocker, capsys):
    mocker.patch.object(mod, "_snapshot_dict", side_effect=[
        {"missing_summary_total": 1, "catalogs_with_summary": 0, "agenda_missing_summary_total": 1, "agenda_missing_summary_with_items": 0, "agenda_missing_summary_without_items": 1, "non_agenda_missing_summary_total": 0},
        {"missing_summary_total": 0, "catalogs_with_summary": 1, "agenda_missing_summary_total": 0, "agenda_missing_summary_with_items": 0, "agenda_missing_summary_without_items": 0, "non_agenda_missing_summary_total": 0},
    ])
    segment_spy = mocker.patch.object(mod, "_run_segment_city", return_value={"city": "berkeley", "catalog_count": 1, "complete": 1, "empty": 0, "failed": 0, "timed_out": 0})
    mocker.patch.object(mod, "run_summary_hydration_backfill", return_value={"selected": 1, "complete": 1, "cached": 0, "stale": 0, "blocked_low_signal": 0, "blocked_ungrounded": 0, "not_generated_yet": 0, "error": 0, "other": 0})
    mocker.patch.object(sys, "argv", ["staged_hydrate_cities.py", "--city", "berkeley", "--json"])

    exit_code = mod.main()

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["cities"][0]["city"] == "berkeley"
    segment_spy.assert_called_once_with("berkeley", emit_progress=False)


def test_run_segment_city_emits_catalog_progress_when_enabled(mocker, capsys):
    fake_segment_module = mocker.Mock()
    fake_segment_module._catalog_ids_for_city.return_value = [101, 102]
    fake_segment_module._catalog_timeout_seconds.return_value = 7
    fake_segment_module._segment_catalog_subprocess.side_effect = [
        ("complete", 1.25, None),
        ("failed", 2.5, "boom"),
    ]
    mocker.patch.dict(sys.modules, {"scripts.segment_city_corpus": fake_segment_module})

    result = mod._run_segment_city("berkeley", emit_progress=True)

    captured = capsys.readouterr()
    assert result == {
        "city": "berkeley",
        "catalog_count": 2,
        "complete": 1,
        "empty": 0,
        "failed": 1,
        "timed_out": 0,
    }
    assert "[berkeley] segmentation_start catalog_count=2 timeout_seconds=7" in captured.out
    assert "[berkeley] segmentation_catalog_start index=1/2 catalog_id=101" in captured.out
    assert "outcome=complete duration_seconds=1.25" in captured.out
    assert "[berkeley] segmentation_catalog_start index=2/2 catalog_id=102" in captured.out
    assert "outcome=failed duration_seconds=2.50" in captured.out

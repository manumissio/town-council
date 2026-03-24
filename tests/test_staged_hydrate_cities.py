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
    segment_spy = mocker.patch.object(
        mod,
        "_run_segment_city",
        side_effect=lambda city, **kwargs: {
            "city": city,
            "catalog_count": 0,
            "complete": 0,
            "empty": 0,
            "failed": 0,
            "timed_out": 0,
            "resume_after_id": kwargs.get("resume_after_id"),
            "last_catalog_id": kwargs.get("resume_after_id"),
        },
    )
    summary_spy = mocker.patch.object(mod, "run_summary_hydration_backfill", side_effect=lambda **kwargs: {"selected": 1, "complete": 1, "cached": 0, "stale": 0, "blocked_low_signal": 0, "blocked_ungrounded": 0, "not_generated_yet": 0, "error": 0, "other": 0})
    mocker.patch.object(sys, "argv", ["staged_hydrate_cities.py"])

    exit_code = mod.main()

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "[hayward] city_start" in captured.out
    assert "[hayward] before_snapshot" in captured.out
    assert "[hayward] summary_start chunk=1" in captured.out
    assert "[hayward] chunk_finish chunk=1" in captured.out
    assert "[hayward] city_finish" in captured.out
    assert "city: hayward" in captured.out
    assert "city: san_mateo" in captured.out
    assert [call.args[0] for call in segment_spy.call_args_list] == ["hayward", "sunnyvale", "berkeley", "cupertino", "san_mateo"]
    assert [call.kwargs["city"] for call in summary_spy.call_args_list] == ["hayward", "sunnyvale", "berkeley", "cupertino", "san_mateo"]
    assert all(call.kwargs["emit_progress"] is True for call in segment_spy.call_args_list)
    assert all(call.kwargs["chunk_index"] == 1 for call in segment_spy.call_args_list)


def test_staged_hydrate_cities_json_mode(mocker, capsys):
    mocker.patch.object(mod, "_snapshot_dict", side_effect=[
        {"missing_summary_total": 1, "catalogs_with_summary": 0, "agenda_missing_summary_total": 1, "agenda_missing_summary_with_items": 0, "agenda_missing_summary_without_items": 1, "non_agenda_missing_summary_total": 0},
        {"missing_summary_total": 0, "catalogs_with_summary": 1, "agenda_missing_summary_total": 0, "agenda_missing_summary_with_items": 0, "agenda_missing_summary_without_items": 0, "non_agenda_missing_summary_total": 0},
    ])
    segment_spy = mocker.patch.object(
        mod,
        "_run_segment_city",
        return_value={
            "city": "berkeley",
            "catalog_count": 0,
            "complete": 0,
            "empty": 0,
            "failed": 0,
            "timed_out": 0,
            "resume_after_id": None,
            "last_catalog_id": None,
        },
    )
    mocker.patch.object(mod, "run_summary_hydration_backfill", return_value={"selected": 1, "complete": 1, "cached": 0, "stale": 0, "blocked_low_signal": 0, "blocked_ungrounded": 0, "not_generated_yet": 0, "error": 0, "other": 0})
    mocker.patch.object(sys, "argv", ["staged_hydrate_cities.py", "--city", "berkeley", "--json"])

    exit_code = mod.main()

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["cities"][0]["city"] == "berkeley"
    assert payload["cities"][0]["chunks"][0]["chunk_index"] == 1
    segment_spy.assert_called_once_with(
        "berkeley",
        limit=None,
        resume_after_id=None,
        workers=None,
        emit_progress=False,
        chunk_index=1,
    )


def test_run_segment_city_emits_catalog_progress_when_enabled(mocker, capsys):
    fake_segment_module = mocker.Mock()
    fake_segment_module._catalog_ids_for_city.return_value = [101, 102]
    fake_segment_module._prioritized_catalog_ids.return_value = [101, 102]
    fake_segment_module._catalog_timeout_seconds.return_value = 7
    fake_segment_module._catalog_worker_count.return_value = 2

    def _segment_catalog_batch(city, catalog_ids, *, timeout_seconds, workers, progress_callback):
        progress_callback(city, 1, 2, 101, "complete", 1.25)
        progress_callback(city, 2, 2, 102, "failed", 2.5)
        return {"city": city, "catalog_count": 2, "complete": 1, "empty": 0, "failed": 1, "timed_out": 0}

    fake_segment_module._segment_catalog_batch.side_effect = _segment_catalog_batch
    mocker.patch.dict(sys.modules, {"scripts.segment_city_corpus": fake_segment_module})

    result = mod._run_segment_city("berkeley", emit_progress=True, chunk_index=1)

    captured = capsys.readouterr()
    assert result == {
        "city": "berkeley",
        "catalog_count": 2,
        "complete": 1,
        "empty": 0,
        "failed": 1,
        "timed_out": 0,
        "resume_after_id": None,
        "last_catalog_id": 102,
    }
    assert "[berkeley] segmentation_start chunk=1 catalog_count=2 timeout_seconds=7 workers=2 resume_after_id=None" in captured.out
    assert "[berkeley] segmentation_catalog_start chunk=1 index=1/2 catalog_id=101" in captured.out
    assert "outcome=complete duration_seconds=1.25" in captured.out
    assert "[berkeley] segmentation_catalog_start chunk=1 index=2/2 catalog_id=102" in captured.out
    assert "outcome=failed duration_seconds=2.50" in captured.out


def test_staged_hydrate_cities_runs_multiple_chunks_and_bounds_summary(mocker, capsys):
    mocker.patch.object(
        mod,
        "_snapshot_dict",
        side_effect=[
            {"missing_summary_total": 10, "catalogs_with_summary": 0, "agenda_missing_summary_total": 10, "agenda_missing_summary_with_items": 0, "agenda_missing_summary_without_items": 10, "non_agenda_missing_summary_total": 0},
            {"missing_summary_total": 8, "catalogs_with_summary": 2, "agenda_missing_summary_total": 8, "agenda_missing_summary_with_items": 0, "agenda_missing_summary_without_items": 8, "non_agenda_missing_summary_total": 0},
            {"missing_summary_total": 7, "catalogs_with_summary": 3, "agenda_missing_summary_total": 7, "agenda_missing_summary_with_items": 0, "agenda_missing_summary_without_items": 7, "non_agenda_missing_summary_total": 0},
        ],
    )
    segment_spy = mocker.patch.object(
        mod,
        "_run_segment_city",
        side_effect=[
            {"city": "berkeley", "catalog_count": 2, "complete": 2, "empty": 0, "failed": 0, "timed_out": 0, "resume_after_id": None, "last_catalog_id": 20},
            {"city": "berkeley", "catalog_count": 0, "complete": 0, "empty": 0, "failed": 0, "timed_out": 0, "resume_after_id": 20, "last_catalog_id": 20},
        ],
    )
    summary_spy = mocker.patch.object(
        mod,
        "run_summary_hydration_backfill",
        side_effect=[
            {"selected": 5, "complete": 2, "cached": 0, "stale": 0, "blocked_low_signal": 0, "blocked_ungrounded": 0, "not_generated_yet": 0, "error": 0, "other": 0},
            {"selected": 5, "complete": 1, "cached": 0, "stale": 0, "blocked_low_signal": 0, "blocked_ungrounded": 0, "not_generated_yet": 0, "error": 0, "other": 0},
        ],
    )
    mocker.patch.object(sys, "argv", ["staged_hydrate_cities.py", "--city", "berkeley", "--segment-limit", "2", "--summary-limit", "5", "--json"])

    exit_code = mod.main()

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["cities"][0]["segmentation"]["catalog_count"] == 2
    assert payload["cities"][0]["summary"]["selected"] == 10
    assert [chunk["chunk_index"] for chunk in payload["cities"][0]["chunks"]] == [1, 2]
    assert segment_spy.call_args_list[0].kwargs["resume_after_id"] is None
    assert segment_spy.call_args_list[1].kwargs["resume_after_id"] == 20
    assert all(call.kwargs["limit"] == 5 for call in summary_spy.call_args_list)

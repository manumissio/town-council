import importlib.util
import json
import sys
from pathlib import Path


spec = importlib.util.spec_from_file_location(
    "hydrate_repaired_city_catalogs",
    Path("scripts/hydrate_repaired_city_catalogs.py"),
)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def test_hydrate_repaired_city_catalogs_emits_stage_progress(mocker, capsys):
    mocker.patch.object(
        mod,
        "_run_extract_city",
        return_value={
            "selected": 3,
            "updated": 2,
            "cached": 0,
            "missing_file": 0,
            "zero_byte": 1,
            "missing_catalog": 0,
            "failed": 0,
            "other": 0,
        },
    )
    mocker.patch.object(
        mod,
        "_run_segment_city",
        return_value={"selected": 2, "complete": 1, "empty": 1, "failed": 0, "other": 0},
    )
    mocker.patch.object(
        mod,
        "_run_summary_city",
        return_value={
            "selected": 1,
            "complete": 1,
            "cached": 0,
            "stale": 0,
            "blocked_low_signal": 0,
            "blocked_ungrounded": 0,
            "not_generated_yet": 0,
            "error": 0,
            "other": 0,
        },
    )
    mocker.patch.object(sys, "argv", ["hydrate_repaired_city_catalogs.py", "--city", "san_mateo"])

    exit_code = mod.main()

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "[san_mateo] hydrate_finish payload=" in captured.out
    assert "'updated': 2" in captured.out


def test_run_extract_city_emits_progress_and_counts(mocker, capsys):
    mocker.patch.object(mod, "_select_extract_catalog_ids", return_value=[101, 102, 103])
    mocker.patch.object(
        mod,
        "_extract_one_catalog",
        side_effect=[
            ("updated", {"status": "updated"}),
            ("zero_byte", {"error": "Zero-byte file on disk"}),
            ("failed", {"error": "Extraction returned empty text"}),
        ],
    )

    result = mod._run_extract_city(
        "san_mateo",
        limit=3,
        resume_after_id=100,
        emit_progress=True,
        progress_every=2,
    )

    captured = capsys.readouterr()
    assert result == {
        "selected": 3,
        "updated": 1,
        "cached": 0,
        "missing_file": 0,
        "zero_byte": 1,
        "missing_catalog": 0,
        "failed": 1,
        "other": 0,
    }
    assert "[san_mateo] extract_start selected=3 limit=3 resume_after_id=100" in captured.out
    assert "[san_mateo] extract_progress done=1/3 last_catalog_id=101 last_status=updated" in captured.out
    assert "[san_mateo] extract_progress done=2/3 last_catalog_id=102 last_status=zero_byte" in captured.out
    assert "[san_mateo] extract_progress done=3/3 last_catalog_id=103 last_status=failed" in captured.out
    assert "[san_mateo] extract_finish counts=" in captured.out


def test_hydrate_repaired_city_catalogs_json_mode(mocker, capsys):
    mocker.patch.object(
        mod,
        "_run_extract_city",
        return_value={
            "selected": 0,
            "updated": 0,
            "cached": 0,
            "missing_file": 0,
            "zero_byte": 0,
            "missing_catalog": 0,
            "failed": 0,
            "other": 0,
        },
    )
    mocker.patch.object(mod, "_run_segment_city", return_value={"selected": 0, "complete": 0, "empty": 0, "failed": 0, "other": 0})
    mocker.patch.object(
        mod,
        "_run_summary_city",
        return_value={
            "selected": 0,
            "complete": 0,
            "cached": 0,
            "stale": 0,
            "blocked_low_signal": 0,
            "blocked_ungrounded": 0,
            "not_generated_yet": 0,
            "error": 0,
            "other": 0,
        },
    )
    mocker.patch.object(sys, "argv", ["hydrate_repaired_city_catalogs.py", "--city", "san_mateo", "--json"])

    exit_code = mod.main()

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["city"] == "san_mateo"
    assert payload["extract"]["selected"] == 0

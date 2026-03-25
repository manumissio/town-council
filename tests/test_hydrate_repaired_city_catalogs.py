import importlib.util
import json
import sys
from contextlib import contextmanager
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
        return_value=(
            {
                "selected": 3,
                "updated": 2,
                "cached": 0,
                "missing_file": 0,
                "zero_byte": 1,
                "missing_catalog": 0,
                "failed": 0,
                "other": 0,
            },
            [101, 102],
        ),
    )
    segment_spy = mocker.patch.object(
        mod,
        "_run_segment_city",
        return_value={
            "selected": 2,
            "complete": 1,
            "empty": 1,
            "failed": 0,
            "other": 0,
            "timeout_fallbacks": 3,
            "empty_response_fallbacks": 1,
        },
    )
    summary_spy = mocker.patch.object(
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
    mocker.patch.object(
        sys,
        "argv",
        [
            "hydrate_repaired_city_catalogs.py",
            "--city",
            "san_mateo",
            "--extract-workers",
            "3",
            "--segment-workers",
            "1",
            "--agenda-timeout-seconds",
            "20",
        ],
    )
    mocker.patch.object(mod.time, "perf_counter", side_effect=[0.0, 2.0, 2.0, 5.0, 5.0, 9.0])

    exit_code = mod.main()

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "[san_mateo] hydrate_finish payload=" in captured.out
    assert "[san_mateo] extract_timing elapsed_s=2.00" in captured.out
    assert "'updated': 2" in captured.out
    assert segment_spy.call_args.kwargs["catalog_ids"] == [101, 102]
    assert segment_spy.call_args.kwargs["workers"] == 1
    assert segment_spy.call_args.kwargs["agenda_timeout_seconds"] == 20
    assert summary_spy.call_args.kwargs["catalog_ids"] == [101, 102]


def test_run_extract_city_emits_progress_and_counts(mocker, capsys):
    mocker.patch.object(
        mod,
        "_select_extract_catalog_ids",
        return_value=([101, 102, 103], {"missing_file": 2, "zero_byte": 4}),
    )
    mocker.patch.object(
        mod,
        "_extract_one_catalog",
        side_effect=[
            ("updated", {"status": "updated"}),
            ("zero_byte", {"error": "Zero-byte file on disk"}),
            ("failed", {"error": "Extraction returned empty text"}),
        ],
    )

    result, ready_ids = mod._run_extract_city(
        "san_mateo",
        limit=3,
        resume_after_id=100,
        emit_progress=True,
        progress_every=2,
        workers=2,
    )

    captured = capsys.readouterr()
    assert result == {
        "selected": 3,
        "updated": 1,
        "cached": 0,
        "missing_file": 2,
        "zero_byte": 5,
        "missing_catalog": 0,
        "failed": 1,
        "other": 0,
    }
    assert ready_ids == [101]
    assert "[san_mateo] extract_start selected=3 limit=3 resume_after_id=100" in captured.out
    assert "[san_mateo] extract_progress done=1/3" in captured.out
    assert "last_status=updated" in captured.out
    assert "[san_mateo] extract_progress done=2/3" in captured.out
    assert "last_status=zero_byte" in captured.out
    assert "[san_mateo] extract_progress done=3/3" in captured.out
    assert "last_status=failed" in captured.out
    assert "[san_mateo] extract_finish counts=" in captured.out


def test_hydrate_repaired_city_catalogs_json_mode(mocker, capsys):
    mocker.patch.object(
        mod,
        "_run_extract_city",
        return_value=(
            {
                "selected": 0,
                "updated": 0,
                "cached": 0,
                "missing_file": 0,
                "zero_byte": 0,
                "missing_catalog": 0,
                "failed": 0,
                "other": 0,
            },
            [],
        ),
    )
    mocker.patch.object(
        mod,
        "_run_segment_city",
        return_value={
            "selected": 0,
            "complete": 0,
            "empty": 0,
            "failed": 0,
            "other": 0,
            "timeout_fallbacks": 0,
            "empty_response_fallbacks": 0,
        },
    )
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
    mocker.patch.object(mod.time, "perf_counter", side_effect=[0.0, 1.0, 1.0, 2.0, 2.0, 3.0])

    exit_code = mod.main()

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["city"] == "san_mateo"
    assert payload["extract"]["selected"] == 0
    assert payload["timing"]["extract_seconds"] == 1.0


def test_run_segment_city_counts_fallback_events(mocker, capsys):
    mocker.patch.object(mod, "_select_segment_catalog_ids", return_value=[101, 102, 103])
    mocker.patch.object(mod, "_segment_one_catalog", side_effect=["complete", "empty", "complete"])

    @contextmanager
    def _fake_timeout(timeout_seconds):
        assert timeout_seconds == 15
        yield

    @contextmanager
    def _fake_capture():
        yield {"timeout": 2, "empty_response": 1}

    mocker.patch.object(mod, "_segment_timeout_override", _fake_timeout)
    mocker.patch.object(mod, "_capture_agenda_fallback_events", _fake_capture)

    counts = mod._run_segment_city(
        "san_mateo",
        limit=3,
        resume_after_id=100,
        emit_progress=True,
        progress_every=2,
        catalog_ids=[101, 102, 103],
        workers=2,
        agenda_timeout_seconds=15,
    )

    captured = capsys.readouterr()
    assert counts["complete"] == 2
    assert counts["empty"] == 1
    assert counts["timeout_fallbacks"] == 2
    assert counts["empty_response_fallbacks"] == 1
    assert "[san_mateo] segment_progress done=2/3" in captured.out


def test_segment_timeout_override_is_scoped(mocker):
    previous_provider = object()
    previous_instance = type("Instance", (), {"_provider": previous_provider, "_provider_backend": "http"})()
    mocker.patch.object(mod.llm_mod.LocalAI, "_instance", previous_instance)
    previous_timeout = mod.llm_provider_mod.LOCAL_AI_HTTP_TIMEOUT_SEGMENT_SECONDS

    with mod._segment_timeout_override(17):
        assert mod.llm_provider_mod.LOCAL_AI_HTTP_TIMEOUT_SEGMENT_SECONDS == 17
        assert previous_instance._provider is None
        assert previous_instance._provider_backend is None

    assert mod.llm_provider_mod.LOCAL_AI_HTTP_TIMEOUT_SEGMENT_SECONDS == previous_timeout
    assert previous_instance._provider is previous_provider
    assert previous_instance._provider_backend == "http"

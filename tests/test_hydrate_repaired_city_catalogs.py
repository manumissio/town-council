import importlib.util
import json
import sys
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace


spec = importlib.util.spec_from_file_location(
    "hydrate_repaired_city_catalogs",
    Path("scripts/hydrate_repaired_city_catalogs.py"),
)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


class _FakeRunStatus:
    def __init__(self, *, tool_name, output_dir, run_id, metadata):
        self.tool_name = tool_name
        self.run_id = run_id or "test_run"
        self.metadata = metadata
        self.paths = SimpleNamespace(run_dir=Path(output_dir) / tool_name / self.run_id)
        self.events = []
        self.heartbeats = []
        self.results = []

    def heartbeat(self, **payload):
        self.heartbeats.append(payload)

    def event(self, **payload):
        self.events.append(payload)

    def result(self, **payload):
        self.results.append(payload)


def test_hydrate_repaired_city_catalogs_emits_stage_progress(mocker, capsys):
    fake_run = _FakeRunStatus(
        tool_name="hydrate_repaired_city_catalogs",
        output_dir="experiments/results/maintenance",
        run_id="test_run",
        metadata={},
    )
    mocker.patch.object(mod, "MaintenanceRunStatus", return_value=fake_run)
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
            "llm_attempted": 1,
            "llm_skipped_heuristic_first": 1,
            "heuristic_complete": 1,
            "llm_timeout_then_fallback": 3,
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
            "llm_complete": 1,
            "deterministic_fallback_complete": 0,
        },
    )
    mocker.patch.object(
        sys,
        "argv",
        [
            "hydrate_repaired_city_catalogs.py",
            "--city",
            "san_mateo",
            "--url-substring",
            "ElectronicFile.aspx",
            "--extract-workers",
            "3",
            "--segment-workers",
            "1",
            "--segment-mode",
            "maintenance",
            "--agenda-timeout-seconds",
            "20",
            "--summary-timeout-seconds",
            "35",
            "--summary-fallback-mode",
            "deterministic",
        ],
    )
    mocker.patch.object(mod.time, "perf_counter", side_effect=[0.0, 0.0, 2.0, 2.0, 5.0, 5.0, 9.0, 9.5])

    exit_code = mod.main()

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "[san_mateo] run_status run_id=test_run artifact_dir=experiments/results/maintenance/hydrate_repaired_city_catalogs/test_run" in captured.out
    assert "[san_mateo] hydrate_finish payload=" in captured.out
    assert "selector_mode': 'url_substring:ElectronicFile.aspx'" in captured.out
    assert "[san_mateo] extract_timing elapsed_s=2.00" in captured.out
    assert "'updated': 2" in captured.out
    assert segment_spy.call_args.kwargs["url_substring"] == "ElectronicFile.aspx"
    assert segment_spy.call_args.kwargs["catalog_ids"] == [101, 102]
    assert segment_spy.call_args.kwargs["workers"] == 1
    assert segment_spy.call_args.kwargs["agenda_timeout_seconds"] == 20
    assert segment_spy.call_args.kwargs["segment_mode"] == "maintenance"
    assert summary_spy.call_args.kwargs["url_substring"] == "ElectronicFile.aspx"
    assert summary_spy.call_args.kwargs["catalog_ids"] == [101, 102]
    assert summary_spy.call_args.kwargs["summary_timeout_seconds"] == 35
    assert summary_spy.call_args.kwargs["summary_fallback_mode"] == "deterministic"


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
        url_substring=None,
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
    assert "selector='city_agenda_repair'" in captured.out
    assert "[san_mateo] extract_progress done=1/3" in captured.out
    assert "last_status=updated" in captured.out
    assert "[san_mateo] extract_progress done=2/3" in captured.out
    assert "last_status=zero_byte" in captured.out
    assert "[san_mateo] extract_progress done=3/3" in captured.out
    assert "last_status=failed" in captured.out
    assert "[san_mateo] extract_finish counts=" in captured.out


def test_hydrate_repaired_city_catalogs_json_mode(mocker, capsys):
    fake_run = _FakeRunStatus(
        tool_name="hydrate_repaired_city_catalogs",
        output_dir="experiments/results/maintenance",
        run_id="json_run",
        metadata={},
    )
    mocker.patch.object(mod, "MaintenanceRunStatus", return_value=fake_run)
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
            "llm_attempted": 0,
            "llm_skipped_heuristic_first": 0,
            "heuristic_complete": 0,
            "llm_timeout_then_fallback": 0,
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
            "llm_complete": 0,
            "deterministic_fallback_complete": 0,
        },
    )
    mocker.patch.object(
        sys,
        "argv",
        [
            "hydrate_repaired_city_catalogs.py",
            "--city",
            "san_mateo",
            "--url-substring",
            "View.ashx?M=A",
            "--json",
        ],
    )
    mocker.patch.object(mod.time, "perf_counter", side_effect=[0.0, 0.0, 1.0, 1.0, 2.0, 2.0, 3.0, 3.5])

    exit_code = mod.main()

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["city"] == "san_mateo"
    assert payload["selector_mode"] == "url_substring:View.ashx?M=A"
    assert payload["url_substring"] == "View.ashx?M=A"
    assert payload["extract"]["selected"] == 0
    assert payload["timing"]["extract_seconds"] == 1.0


def test_run_segment_city_counts_fallback_events(mocker, capsys):
    mocker.patch.object(mod, "_select_segment_catalog_ids", return_value=[101, 102, 103])
    mocker.patch.object(
        mod,
        "_segment_one_catalog",
        side_effect=[
            {"status": "complete", "llm_attempted": 1, "llm_skipped_heuristic_first": 0, "heuristic_complete": 0},
            {"status": "empty", "llm_attempted": 0, "llm_skipped_heuristic_first": 1, "heuristic_complete": 0},
            {"status": "complete", "llm_attempted": 0, "llm_skipped_heuristic_first": 1, "heuristic_complete": 1},
        ],
    )

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
        url_substring=None,
        emit_progress=True,
        progress_every=2,
        catalog_ids=[101, 102, 103],
        workers=2,
        agenda_timeout_seconds=15,
        segment_mode="maintenance",
    )

    captured = capsys.readouterr()
    assert counts["complete"] == 2
    assert counts["empty"] == 1
    assert counts["timeout_fallbacks"] == 2
    assert counts["empty_response_fallbacks"] == 1
    assert counts["llm_attempted"] == 1
    assert counts["llm_skipped_heuristic_first"] == 2
    assert counts["heuristic_complete"] == 1
    assert counts["llm_timeout_then_fallback"] == 2
    assert "[san_mateo] segment_progress done=2/3" in captured.out
    assert "selector='city_agenda_repair'" in captured.out


def test_heuristic_segment_gate_prefers_structured_text():
    structured = "\n".join(
        [
            "[PAGE 1]",
            "1. Call to Order",
            "2. Budget Amendment",
            "3. Zoning Update",
            "4. Capital Improvement Plan",
        ]
    )
    weak = "Short memo without obvious agenda markers."

    assert mod._looks_structured_enough_for_heuristic_segmentation(structured) is True
    assert mod._looks_structured_enough_for_heuristic_segmentation(weak) is False


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


def test_summarize_one_catalog_converts_retry_exception_to_error(mocker):
    mocker.patch.object(mod.generate_summary_task, "run", side_effect=RuntimeError("retry-called"))

    result = mod._summarize_one_catalog(101)

    assert result == {"status": "error", "error": "retry-called"}


def test_summarize_one_catalog_uses_deterministic_fallback_on_timeout(mocker):
    @contextmanager
    def _fake_capture():
        yield {"timeout": 1}

    mocker.patch.object(mod, "_capture_summary_fallback_events", _fake_capture)
    mocker.patch.object(mod.generate_summary_task, "run", side_effect=RuntimeError("retry-called"))
    fallback_spy = mocker.patch.object(
        mod,
        "_build_deterministic_agenda_summary_payload",
        return_value={"status": "complete", "summary": "fallback", "completion_mode": "deterministic_fallback"},
    )

    result = mod._summarize_one_catalog(101, summary_fallback_mode="deterministic")

    assert result["status"] == "complete"
    assert result["completion_mode"] == "deterministic_fallback"
    fallback_spy.assert_called_once()
    assert fallback_spy.call_args.args == (101,)


def test_run_summary_city_continues_after_summary_error(mocker, capsys):
    mocker.patch.object(mod, "_select_summary_catalog_ids", return_value=[101, 102, 103])
    mocker.patch.object(
        mod,
        "_summarize_one_catalog",
        side_effect=[
            {"status": "complete", "summary": "ok", "completion_mode": "llm"},
            {"status": "error", "error": "retry-called"},
            {"status": "complete", "summary": "fallback", "completion_mode": "deterministic_fallback"},
        ],
    )

    @contextmanager
    def _fake_timeout(timeout_seconds):
        assert timeout_seconds == 25
        yield

    mocker.patch.object(mod, "_summary_timeout_override", _fake_timeout)

    counts = mod._run_summary_city(
        "san_mateo",
        limit=3,
        resume_after_id=100,
        url_substring=None,
        emit_progress=True,
        progress_every=2,
        catalog_ids=[101, 102, 103],
        summary_timeout_seconds=25,
        summary_fallback_mode="deterministic",
    )

    captured = capsys.readouterr()
    assert counts["complete"] == 2
    assert counts["error"] == 1
    assert counts["llm_complete"] == 1
    assert counts["deterministic_fallback_complete"] == 1
    assert "last_error='retry-called'" in captured.out
    assert "selector='city_agenda_repair'" in captured.out


def test_summary_timeout_override_is_scoped(mocker):
    previous_provider = object()
    previous_instance = type("Instance", (), {"_provider": previous_provider, "_provider_backend": "http"})()
    mocker.patch.object(mod.llm_mod.LocalAI, "_instance", previous_instance)
    previous_timeout = mod.llm_provider_mod.LOCAL_AI_HTTP_TIMEOUT_SUMMARY_SECONDS

    with mod._summary_timeout_override(29):
        assert mod.llm_provider_mod.LOCAL_AI_HTTP_TIMEOUT_SUMMARY_SECONDS == 29
        assert previous_instance._provider is None
        assert previous_instance._provider_backend is None

    assert mod.llm_provider_mod.LOCAL_AI_HTTP_TIMEOUT_SUMMARY_SECONDS == previous_timeout
    assert previous_instance._provider is previous_provider
    assert previous_instance._provider_backend == "http"


def test_selector_mode_defaults_and_url_narrowing():
    assert mod._selector_mode(None) == "city_agenda_repair"
    assert mod._selector_mode("ElectronicFile.aspx") == "url_substring:ElectronicFile.aspx"


def test_select_extract_catalog_ids_defaults_to_any_agenda_url(mocker):
    rows = [(101, "/tmp/agenda.pdf")]

    class FakeQuery:
        def __init__(self):
            self.filters = []

        def join(self, *args, **kwargs):
            return self

        def filter(self, *conditions):
            self.filters.extend(conditions)
            return self

        def order_by(self, *args, **kwargs):
            return self

        def all(self):
            return rows

    query = FakeQuery()

    @contextmanager
    def fake_db_session():
        yield SimpleNamespace(query=lambda *args, **kwargs: query)

    mocker.patch.object(mod, "db_session", fake_db_session)
    mocker.patch.object(mod, "_usable_local_artifact_status", return_value=None)

    selected_ids, counts = mod._select_extract_catalog_ids("hayward", limit=None, resume_after_id=None)

    rendered_filters = [str(condition) for condition in query.filters]
    assert selected_ids == [101]
    assert counts == {"missing_file": 0, "zero_byte": 0}
    assert any("document.category" in rendered for rendered in rendered_filters)
    assert all("catalog.url" not in rendered for rendered in rendered_filters)


def test_select_extract_catalog_ids_can_narrow_by_url_substring(mocker):
    rows = [(101, "/tmp/agenda.pdf")]

    class FakeQuery:
        def __init__(self):
            self.filters = []

        def join(self, *args, **kwargs):
            return self

        def filter(self, *conditions):
            self.filters.extend(conditions)
            return self

        def order_by(self, *args, **kwargs):
            return self

        def all(self):
            return rows

    query = FakeQuery()

    @contextmanager
    def fake_db_session():
        yield SimpleNamespace(query=lambda *args, **kwargs: query)

    mocker.patch.object(mod, "db_session", fake_db_session)
    mocker.patch.object(mod, "_usable_local_artifact_status", return_value=None)

    selected_ids, counts = mod._select_extract_catalog_ids(
        "san_mateo",
        limit=None,
        resume_after_id=None,
        url_substring="ElectronicFile.aspx",
    )

    rendered_filters = [str(condition) for condition in query.filters]
    assert selected_ids == [101]
    assert counts == {"missing_file": 0, "zero_byte": 0}
    assert any("catalog.url" in rendered for rendered in rendered_filters)

import importlib.util
import json
import sys
from contextlib import contextmanager
from pathlib import Path

from pipeline import (
    agenda_segmentation_maintenance,
    indexer,
    llm as llm_module,
    llm_provider as llm_provider_module,
    semantic_tasks,
)
from pipeline.models import AgendaItem, Catalog, Document, Event, Place
from scripts import hydration_repaired_runner, hydration_repaired_summary


spec = importlib.util.spec_from_file_location(
    "hydrate_repaired_city_catalogs",
    Path("scripts/hydrate_repaired_city_catalogs.py"),
)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def _seed_city_event(db_session, city):
    place = Place(
        name=city,
        state="CA",
        ocd_division_id=f"ocd-division/country:us/state:ca/place:{city}",
        crawler_name=city,
    )
    db_session.add(place)
    db_session.flush()
    event = Event(
        place_id=place.id,
        ocd_division_id=place.ocd_division_id,
        name=f"{city.title()} Council",
        source=city,
    )
    db_session.add(event)
    db_session.flush()
    return place, event


def _add_agenda_catalog(
    db_session,
    place,
    event,
    *,
    slug,
    content,
    url_path="ElectronicFile.aspx",
    location=None,
    add_agenda_item=True,
):
    catalog = Catalog(
        url=f"https://portal.laserfiche.com/Portal/{url_path}?id={slug}",
        url_hash=slug,
        location=location or f"/tmp/{slug}.pdf",
        filename=f"{slug}.pdf",
        content=content,
    )
    db_session.add(catalog)
    db_session.flush()
    db_session.add(
        Document(
            place_id=place.id,
            event_id=event.id,
            catalog_id=catalog.id,
            category="agenda",
            url=catalog.url,
        )
    )
    if add_agenda_item:
        db_session.add(
            AgendaItem(
                event_id=event.id,
                catalog_id=catalog.id,
                order=1,
                title=f"Approve {slug} budget",
                description="Review funding and authorize the proposed budget.",
                classification="Action",
                page_number=1,
            )
        )
    return catalog


def _install_summary_boundaries(mocker):
    mocker.patch.object(llm_module.LocalAI, "_instance", None)
    provider_lookup = mocker.patch.object(
        llm_module,
        "get_runtime_provider",
        side_effect=AssertionError("Repaired agenda summaries must not invoke inference"),
    )
    mocker.patch.object(
        indexer.meilisearch,
        "Client",
        side_effect=RuntimeError("search unavailable"),
    )
    embed_dispatch = mocker.patch.object(
        semantic_tasks.embed_catalog_task,
        "delay",
        return_value=None,
    )
    return provider_lookup, embed_dispatch


def test_hydrate_repaired_city_catalogs_emits_stage_progress(
    db_session,
    mocker,
    capsys,
    tmp_path,
):
    place, event = _seed_city_event(db_session, "san_mateo")
    catalog = _add_agenda_catalog(
        db_session,
        place,
        event,
        slug="progress-agenda",
        content="[PAGE 1]\n1. Approve the annual budget",
    )
    db_session.commit()
    provider_lookup, embed_dispatch = _install_summary_boundaries(mocker)
    mocker.patch.object(
        mod,
        "_run_extract_city",
        return_value=(
            {
                "selected": 1,
                "updated": 1,
                "cached": 0,
                "missing_file": 0,
                "zero_byte": 0,
                "missing_catalog": 0,
                "failed": 0,
                "other": 0,
            },
            [catalog.id],
        ),
    )
    segment_spy = mocker.patch.object(
        mod,
        "_run_segment_city",
        return_value={
            "selected": 1,
            "complete": 1,
            "empty": 0,
            "failed": 0,
            "other": 0,
            "timeout_fallbacks": 0,
            "empty_response_fallbacks": 0,
            "llm_attempted": 0,
            "llm_skipped_heuristic_first": 0,
            "heuristic_complete": 1,
            "llm_timeout_then_fallback": 0,
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
            "--output-dir",
            str(tmp_path),
            "--run-id",
            "test_run",
        ],
    )
    mocker.patch.object(
        hydration_repaired_runner.time,
        "perf_counter",
        side_effect=[0.0, 0.0, 2.0, 2.0, 5.0, 5.0, 9.0, 9.5],
    )

    exit_code = mod.main()

    captured = capsys.readouterr()
    run_dir = tmp_path / "hydrate_repaired_city_catalogs" / "test_run"
    result_payload = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
    manifest_payload = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    assert exit_code == 0
    assert f"[san_mateo] run_status run_id=test_run artifact_dir={run_dir}" in captured.out
    assert "[san_mateo] hydrate_finish payload=" in captured.out
    assert "selector_mode': 'url_substring:ElectronicFile.aspx'" in captured.out
    assert "[san_mateo] extract_timing elapsed_s=2.00" in captured.out
    assert "'agenda_deterministic_complete': 1" in captured.out
    assert segment_spy.call_args.kwargs["url_substring"] == "ElectronicFile.aspx"
    assert segment_spy.call_args.kwargs["catalog_ids"] == [catalog.id]
    assert segment_spy.call_args.kwargs["workers"] == 1
    assert segment_spy.call_args.kwargs["agenda_timeout_seconds"] == 20
    assert segment_spy.call_args.kwargs["segment_mode"] == "maintenance"
    assert result_payload["counts"]["summary"]["complete"] == 1
    assert result_payload["counts"]["summary"]["agenda_deterministic_complete"] == 1
    assert result_payload["counts"]["summary_timeout_seconds"] == 35
    assert result_payload["counts"]["summary_fallback_mode"] == "deterministic"
    assert manifest_payload["metadata"]["args"]["summary_timeout_seconds"] == 35
    assert manifest_payload["metadata"]["args"]["summary_fallback_mode"] == "deterministic"
    db_session.expire_all()
    assert db_session.get(Catalog, catalog.id).summary.startswith("BLUF:")
    provider_lookup.assert_not_called()
    embed_dispatch.assert_called_once_with(catalog.id)


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


def test_hydrate_repaired_city_catalogs_json_mode(mocker, capsys, tmp_path):
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
        sys,
        "argv",
        [
            "hydrate_repaired_city_catalogs.py",
            "--city",
            "san_mateo",
            "--url-substring",
            "View.ashx?M=A",
            "--json",
            "--output-dir",
            str(tmp_path),
            "--run-id",
            "json_run",
        ],
    )
    mocker.patch.object(
        hydration_repaired_runner.time,
        "perf_counter",
        side_effect=[0.0, 0.0, 1.0, 1.0, 2.0, 2.0, 3.0, 3.5],
    )

    exit_code = mod.main()

    payload = json.loads(capsys.readouterr().out)
    result_path = (
        tmp_path
        / "hydrate_repaired_city_catalogs"
        / "json_run"
        / "result.json"
    )
    assert exit_code == 0
    assert payload["city"] == "san_mateo"
    assert payload["selector_mode"] == "url_substring:View.ashx?M=A"
    assert payload["url_substring"] == "View.ashx?M=A"
    assert payload["extract"]["selected"] == 0
    assert payload["summary"]["selected"] == 0
    assert payload["timing"]["extract_seconds"] == 1.0
    assert json.loads(result_path.read_text(encoding="utf-8"))["status"] == "completed"


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
    assert "timed_out" not in counts
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
    mocker.patch.object(llm_module.LocalAI, "_instance", previous_instance)
    previous_timeout = llm_provider_module.LOCAL_AI_HTTP_TIMEOUT_SEGMENT_SECONDS

    with agenda_segmentation_maintenance.segment_timeout_override(17):
        assert llm_provider_module.LOCAL_AI_HTTP_TIMEOUT_SEGMENT_SECONDS == 17
        assert previous_instance._provider is None
        assert previous_instance._provider_backend is None

    assert llm_provider_module.LOCAL_AI_HTTP_TIMEOUT_SEGMENT_SECONDS == previous_timeout
    assert previous_instance._provider is previous_provider
    assert previous_instance._provider_backend == "http"


def test_run_summary_city_selects_repaired_agendas_and_continues_after_error(
    db_session,
    mocker,
    capsys,
):
    place, event = _seed_city_event(db_session, "san_mateo")
    first_catalog = _add_agenda_catalog(
        db_session,
        place,
        event,
        slug="first-valid-agenda",
        content="[PAGE 1]\n1. Approve the housing budget",
    )
    failed_catalog = _add_agenda_catalog(
        db_session,
        place,
        event,
        slug="poisoned-agenda",
        content=(
            "The system has encountered an error and could not complete your request. "
            "If the problem persists, please contact the site administrator."
        ),
        location="/tmp/poisoned-agenda.html",
    )
    last_catalog = _add_agenda_catalog(
        db_session,
        place,
        event,
        slug="last-valid-agenda",
        content="[PAGE 1]\n1. Approve transportation funding",
    )
    other_place, other_event = _seed_city_event(db_session, "hayward")
    other_city_catalog = _add_agenda_catalog(
        db_session,
        other_place,
        other_event,
        slug="other-city-agenda",
        content="[PAGE 1]\n1. Approve another city budget",
    )
    db_session.commit()
    provider_lookup, embed_dispatch = _install_summary_boundaries(mocker)
    status_events = []

    counts = hydration_repaired_summary.run_summary_city(
        "san_mateo",
        limit=None,
        resume_after_id=None,
        url_substring="ElectronicFile.aspx",
        emit_progress_enabled=True,
        progress_every=2,
        summary_timeout_seconds=25,
        summary_fallback_mode="deterministic",
        status_callback=status_events.append,
    )

    captured = capsys.readouterr()
    assert counts["complete"] == 2
    assert counts["error"] == 1
    assert counts["agenda_deterministic_complete"] == 2
    assert counts["llm_complete"] == 0
    assert counts["deterministic_fallback_complete"] == 0
    assert "last_error='laserfiche_error_page_detected'" in captured.out
    assert "selector='url_substring:ElectronicFile.aspx'" in captured.out
    assert [event["event_type"] for event in status_events] == [
        "stage_start",
        "progress",
        "progress",
        "progress",
        "stage_finish",
    ]
    db_session.expire_all()
    assert db_session.get(Catalog, first_catalog.id).summary.startswith("BLUF:")
    assert db_session.get(Catalog, failed_catalog.id).summary is None
    assert db_session.get(Catalog, last_catalog.id).summary.startswith("BLUF:")
    assert db_session.get(Catalog, other_city_catalog.id).summary is None
    provider_lookup.assert_not_called()
    assert [call.args for call in embed_dispatch.call_args_list] == [
        (first_catalog.id,),
        (last_catalog.id,),
    ]


def test_run_summary_city_applies_resume_limit_and_url_selection(
    db_session,
    mocker,
):
    place, event = _seed_city_event(db_session, "san_mateo")
    first_catalog = _add_agenda_catalog(
        db_session,
        place,
        event,
        slug="selection-first",
        content="[PAGE 1]\n1. First agenda",
    )
    excluded_url_catalog = _add_agenda_catalog(
        db_session,
        place,
        event,
        slug="selection-view",
        content="[PAGE 1]\n1. View agenda",
        url_path="View.ashx?M=A",
    )
    selected_catalog = _add_agenda_catalog(
        db_session,
        place,
        event,
        slug="selection-last",
        content="[PAGE 1]\n1. Selected agenda",
    )
    db_session.commit()
    _install_summary_boundaries(mocker)

    counts = hydration_repaired_summary.run_summary_city(
        "san_mateo",
        limit=1,
        resume_after_id=first_catalog.id,
        url_substring="ElectronicFile.aspx",
        emit_progress_enabled=False,
        progress_every=1,
        summary_fallback_mode="none",
    )

    assert counts["selected"] == 1
    assert counts["complete"] == 1
    db_session.expire_all()
    assert db_session.get(Catalog, first_catalog.id).summary is None
    assert db_session.get(Catalog, excluded_url_catalog.id).summary is None
    assert db_session.get(Catalog, selected_catalog.id).summary.startswith("BLUF:")


def test_summary_timeout_override_is_scoped(mocker):
    previous_provider = object()
    previous_instance = type("Instance", (), {"_provider": previous_provider, "_provider_backend": "http"})()
    mocker.patch.object(llm_module.LocalAI, "_instance", previous_instance)
    previous_timeout = llm_provider_module.LOCAL_AI_HTTP_TIMEOUT_SUMMARY_SECONDS

    with agenda_segmentation_maintenance.summary_timeout_override(29):
        assert llm_provider_module.LOCAL_AI_HTTP_TIMEOUT_SUMMARY_SECONDS == 29
        assert previous_instance._provider is None
        assert previous_instance._provider_backend is None

    assert llm_provider_module.LOCAL_AI_HTTP_TIMEOUT_SUMMARY_SECONDS == previous_timeout
    assert previous_instance._provider is previous_provider
    assert previous_instance._provider_backend == "http"


def test_selector_mode_defaults_and_url_narrowing():
    assert mod._selector_mode(None) == "city_agenda_repair"
    assert mod._selector_mode("ElectronicFile.aspx") == "url_substring:ElectronicFile.aspx"


def test_select_extract_catalog_ids_counts_local_artifact_statuses(
    db_session,
    tmp_path,
):
    place, event = _seed_city_event(db_session, "hayward")
    usable_path = tmp_path / "usable.pdf"
    usable_path.write_bytes(b"agenda")
    zero_byte_path = tmp_path / "zero-byte.pdf"
    zero_byte_path.touch()
    usable_catalog = _add_agenda_catalog(
        db_session,
        place,
        event,
        slug="usable-artifact",
        content=None,
        location=str(usable_path),
        add_agenda_item=False,
    )
    _add_agenda_catalog(
        db_session,
        place,
        event,
        slug="missing-artifact",
        content=None,
        location=str(tmp_path / "missing.pdf"),
        add_agenda_item=False,
    )
    _add_agenda_catalog(
        db_session,
        place,
        event,
        slug="zero-byte-artifact",
        content=None,
        location=str(zero_byte_path),
        add_agenda_item=False,
    )
    db_session.commit()

    selected_ids, counts = mod._select_extract_catalog_ids(
        "hayward",
        limit=None,
        resume_after_id=None,
    )

    assert selected_ids == [usable_catalog.id]
    assert counts == {"missing_file": 1, "zero_byte": 1}


def test_select_extract_catalog_ids_can_narrow_by_url_substring(
    db_session,
    tmp_path,
):
    place, event = _seed_city_event(db_session, "san_mateo")
    electronic_path = tmp_path / "electronic.pdf"
    electronic_path.write_bytes(b"agenda")
    view_path = tmp_path / "view.pdf"
    view_path.write_bytes(b"agenda")
    electronic_catalog = _add_agenda_catalog(
        db_session,
        place,
        event,
        slug="electronic-artifact",
        content=None,
        location=str(electronic_path),
        add_agenda_item=False,
    )
    _add_agenda_catalog(
        db_session,
        place,
        event,
        slug="view-artifact",
        content=None,
        url_path="View.ashx?M=A",
        location=str(view_path),
        add_agenda_item=False,
    )
    db_session.commit()

    selected_ids, counts = mod._select_extract_catalog_ids(
        "san_mateo",
        limit=None,
        resume_after_id=None,
        url_substring="ElectronicFile.aspx",
    )

    assert selected_ids == [electronic_catalog.id]
    assert counts == {"missing_file": 0, "zero_byte": 0}


def test_hydrate_repaired_city_catalogs_does_not_export_summary_patch_seams():
    removed_summary_names = [
        "_run_summary_city",
        "_select_summary_catalog_ids",
        "_summarize_one_catalog",
        "_summary_timeout_override",
        "_summarize_catalog_with_maintenance_mode",
        "llm_mod",
        "llm_provider_mod",
    ]

    assert all(not hasattr(mod, name) for name in removed_summary_names)


def test_hydrate_repaired_implementation_modules_do_not_import_facade():
    module_paths = [
        Path("scripts/hydration_counts.py"),
        Path("scripts/hydration_output.py"),
        Path("scripts/hydration_repaired_extract.py"),
        Path("scripts/hydration_repaired_runner.py"),
        Path("scripts/hydration_repaired_segment.py"),
        Path("scripts/hydration_repaired_selectors.py"),
        Path("scripts/hydration_repaired_summary.py"),
    ]

    for module_path in module_paths:
        assert "scripts.hydrate_repaired_city_catalogs" not in module_path.read_text(encoding="utf-8")

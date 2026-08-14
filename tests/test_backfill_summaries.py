import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

from sqlalchemy.orm import sessionmaker

from pipeline import task_runtime
from pipeline.inference_provider_contract import InferenceProvider, ProviderTimeoutError
from pipeline.models import Catalog, Document, Event, Place


spec = importlib.util.spec_from_file_location(
    "backfill_summaries",
    Path("scripts/backfill_summaries.py"),
)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def _use_test_database(mocker, shared_engine) -> None:
    test_session = sessionmaker(bind=shared_engine)
    mocker.patch.object(task_runtime, "task_session", side_effect=test_session)


def test_backfill_summaries_json_mode_preserves_stdout_and_records_run_status(
    mocker,
    capsys,
    shared_engine,
    tmp_path: Path,
):
    _use_test_database(mocker, shared_engine)
    mocker.patch.object(
        sys,
        "argv",
        [
            "backfill_summaries.py",
            "--city",
            "sunnyvale",
            "--json",
            "--progress-every",
            "5",
            "--run-id",
            "summary_run",
            "--output-dir",
            str(tmp_path),
        ],
    )

    exit_code = mod.main()

    payload = json.loads(capsys.readouterr().out)
    run_dir = tmp_path / "backfill_summaries" / "summary_run"
    heartbeat = json.loads((run_dir / "heartbeat.json").read_text(encoding="utf-8"))
    events = [
        json.loads(event_line)
        for event_line in (run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert exit_code == 0
    assert payload["selected"] == 0
    assert payload["complete"] == 0
    assert heartbeat["status"] == "completed"
    assert events[-1]["event_type"] == "completed"


def test_backfill_summaries_human_mode_prints_run_location(
    mocker,
    capsys,
    shared_engine,
    tmp_path: Path,
):
    _use_test_database(mocker, shared_engine)
    mocker.patch.object(
        sys,
        "argv",
        [
            "backfill_summaries.py",
            "--city",
            "sunnyvale",
            "--run-id",
            "human_run",
            "--output-dir",
            str(tmp_path),
        ],
    )

    exit_code = mod.main()

    captured = capsys.readouterr()
    assert exit_code == 0
    assert f"[summary_backfill] run_status run_id=human_run artifact_dir={tmp_path}/backfill_summaries/human_run" in captured.out
    assert "run_id: human_run" in captured.out
    assert "selected: 0" in captured.out


def test_backfill_summaries_cli_applies_and_records_maintenance_summary_policy(
    mocker,
    capsys,
    db_session,
    shared_engine,
    tmp_path: Path,
):
    from api import task_dispatch
    from pipeline import http_inference_provider, indexer, llm as llm_module

    place = Place(
        name="sunnyvale",
        state="CA",
        ocd_division_id="ocd-division/country:us/state:ca/place:sunnyvale",
        crawler_name="sunnyvale",
    )
    db_session.add(place)
    db_session.flush()
    event = Event(
        place_id=place.id,
        ocd_division_id=place.ocd_division_id,
        name="Sunnyvale City Council",
        source="sunnyvale",
    )
    db_session.add(event)
    db_session.flush()
    catalog = Catalog(
        url_hash="sunnyvale-maintenance-summary-policy",
        location="/tmp/sunnyvale-minutes.pdf",
        content=(
            "Council reviewed housing policy, transportation funding, public safety updates, "
            "budget amendments, and committee recommendations after public comment."
        ),
    )
    db_session.add(catalog)
    db_session.flush()
    db_session.add(
        Document(
            place_id=place.id,
            event_id=event.id,
            catalog_id=catalog.id,
            category="minutes",
            url="https://example.com/sunnyvale-minutes.pdf",
        )
    )
    db_session.commit()

    _use_test_database(mocker, shared_engine)
    mocker.patch.object(indexer.meilisearch, "Client", side_effect=RuntimeError("search unavailable"))
    mocker.patch.object(task_dispatch.celery_app, "send_task", return_value=MagicMock())
    observed_summary_timeouts: list[int] = []
    summary_provider = MagicMock(spec=InferenceProvider)

    def _raise_summary_timeout(*_args, **_kwargs):
        observed_summary_timeouts.append(
            http_inference_provider.LOCAL_AI_HTTP_TIMEOUT_SUMMARY_SECONDS
        )
        raise ProviderTimeoutError("summary timed out")

    summary_provider.summarize_text.side_effect = _raise_summary_timeout
    mocker.patch.object(llm_module, "get_runtime_provider", return_value=summary_provider)
    mocker.patch.object(
        sys,
        "argv",
        [
            "backfill_summaries.py",
            "--city",
            "sunnyvale",
            "--summary-timeout-seconds",
            "5",
            "--summary-fallback-mode",
            "deterministic",
            "--json",
            "--run-id",
            "maintenance_policy",
            "--output-dir",
            str(tmp_path),
        ],
    )

    exit_code = mod.main()

    summary_counts = json.loads(capsys.readouterr().out)
    run_dir = tmp_path / "backfill_summaries" / "maintenance_policy"
    run_manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    db_session.expire_all()
    persisted_catalog = db_session.get(Catalog, catalog.id)
    assert exit_code == 0
    assert observed_summary_timeouts == [5]
    assert summary_counts["selected"] == 1
    assert summary_counts["complete"] == 1
    assert summary_counts["deterministic_fallback_complete"] == 1
    assert persisted_catalog is not None
    assert persisted_catalog.summary is not None
    assert "Deterministic fallback used" in persisted_catalog.summary
    assert run_manifest["metadata"]["args"]["summary_timeout_seconds"] == 5
    assert run_manifest["metadata"]["args"]["summary_fallback_mode"] == "deterministic"

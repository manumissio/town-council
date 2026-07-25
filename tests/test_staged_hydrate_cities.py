import json
import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from pipeline import indexer, llm as llm_module, semantic_tasks, task_runtime
from pipeline.agenda_segmentation_maintenance import HeuristicOnlyLocalAI
from pipeline.models import AgendaItem, Base, Catalog, Document, Event, Place
from pipeline.summary_freshness import compute_agenda_items_hash
from scripts import staged_hydrate_cities, staged_hydration_runner


DEFAULT_CITIES = ("hayward", "sunnyvale", "berkeley", "cupertino", "san_mateo")
STRUCTURED_AGENDA = "\n\n".join(
    f"{agenda_order}. Agenda topic {agenda_order}\nStaff recommends discussing community priority {agenda_order}."
    for agenda_order in range(1, 9)
)


class _SummaryProvider:
    def health_check(self):
        return True

    def extract_agenda(self, prompt, *, temperature, max_tokens):
        raise AssertionError("Agenda extraction is outside these summary-only cases")

    def summarize_agenda_items(self, prompt, *, temperature, max_tokens):
        return "BLUF: Council discussed housing, budget, and public safety priorities."

    def summarize_text(self, prompt, *, temperature, max_tokens):
        return "BLUF: Council discussed housing, budget, and public safety priorities."

    def generate_topics(self, prompt, *, temperature, max_tokens):
        raise AssertionError("Topic generation is outside staged hydration")

    def generate_json(self, prompt, *, max_tokens):
        raise AssertionError("JSON generation is outside staged hydration")


def _install_summary_boundaries(mocker, shared_engine) -> None:
    mocker.patch.object(llm_module.LocalAI, "_instance", None)
    mocker.patch.object(task_runtime, "_session_factory", sessionmaker(bind=shared_engine))
    mocker.patch.object(llm_module, "get_runtime_provider", return_value=_SummaryProvider())
    mocker.patch.object(
        indexer.meilisearch,
        "Client",
        side_effect=RuntimeError("search unavailable"),
    )
    mocker.patch.object(semantic_tasks.embed_catalog_task, "delay", return_value=None)


def _seed_catalogs(
    session,
    *,
    city: str,
    catalog_count: int,
    category: str = "minutes",
    content: str | None = None,
) -> list[Catalog]:
    place = Place(
        name=city,
        state="CA",
        ocd_division_id=f"ocd-division/country:us/state:ca/place:{city}",
        crawler_name=city,
    )
    session.add(place)
    session.flush()
    event = Event(
        place_id=place.id,
        ocd_division_id=place.ocd_division_id,
        name=f"{city.title()} Council",
        source=city,
    )
    session.add(event)
    session.flush()
    catalogs = []
    for catalog_index in range(catalog_count):
        catalog_key = f"{city}-{catalog_index}"
        catalog = Catalog(
            url=f"https://example.test/{catalog_key}",
            url_hash=catalog_key,
            location=f"/tmp/{catalog_key}.pdf",
            filename=f"{catalog_key}.pdf",
            content=content
            or (
                "Council discussed housing budget public safety transportation "
                "priorities and committee recommendations during the meeting."
            ),
        )
        session.add(catalog)
        session.flush()
        session.add(
            Document(
                place_id=place.id,
                event_id=event.id,
                catalog_id=catalog.id,
                category=category,
                url=catalog.url,
            )
        )
        catalogs.append(catalog)
    session.commit()
    return catalogs


def _snapshot(
    *,
    missing_summary_total: int,
    catalogs_with_summary: int,
    agenda_missing_summary_total: int,
    agenda_missing_summary_with_items: int,
    agenda_missing_summary_without_items: int,
    non_agenda_missing_summary_total: int,
    agenda_unresolved_segmentation_status_counts: dict[str, int] | None = None,
) -> dict[str, object]:
    return {
        "missing_summary_total": missing_summary_total,
        "catalogs_with_summary": catalogs_with_summary,
        "agenda_missing_summary_total": agenda_missing_summary_total,
        "agenda_missing_summary_with_items": agenda_missing_summary_with_items,
        "agenda_missing_summary_without_items": agenda_missing_summary_without_items,
        "non_agenda_missing_summary_total": non_agenda_missing_summary_total,
        "agenda_unresolved_segmentation_status_counts": (
            agenda_unresolved_segmentation_status_counts or {"<null>": 0}
        ),
    }


def _seed_file_agenda_database(database_path: Path) -> tuple[str, list[int]]:
    database_url = f"sqlite:///{database_path}"
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    with session_factory() as session:
        catalogs = _seed_catalogs(
            session,
            city="berkeley",
            catalog_count=3,
            category="agenda",
            content=STRUCTURED_AGENDA,
        )
        extracted_items = HeuristicOnlyLocalAI().extract_agenda(STRUCTURED_AGENDA)
        for catalog in catalogs:
            agenda_items = [
                AgendaItem(
                    ocd_id=f"ocd-agenda-item/{catalog.id}-{agenda_item['order']}",
                    event_id=catalog.document.event_id,
                    catalog_id=catalog.id,
                    order=agenda_item["order"],
                    title=agenda_item["title"],
                    description=agenda_item.get("description"),
                )
                for agenda_item in extracted_items
            ]
            session.add_all(agenda_items)
            session.flush()
            agenda_items_hash = compute_agenda_items_hash(agenda_items)
            catalog.agenda_items_hash = agenda_items_hash
            catalog.summary = "Existing deterministic summary."
            catalog.summary_source_hash = agenda_items_hash
        session.commit()
        catalog_ids = [catalog.id for catalog in catalogs]
    engine.dispose()
    return database_url, catalog_ids


def test_staged_hydration_uses_default_city_order_and_reports_progress(
    mocker,
    capsys,
    db_session,
    shared_engine,
):
    for city in DEFAULT_CITIES:
        _seed_catalogs(db_session, city=city, catalog_count=1)
    _install_summary_boundaries(mocker, shared_engine)
    mocker.patch.object(sys, "argv", ["staged_hydrate_cities.py"])

    exit_code = staged_hydrate_cities.main()

    output = capsys.readouterr().out
    assert exit_code == 0
    assert [output.index(f"city: {city}") for city in DEFAULT_CITIES] == sorted(
        output.index(f"city: {city}") for city in DEFAULT_CITIES
    )
    assert "[hayward] summary_start chunk=1" in output
    assert "[hayward] chunk_finish chunk=1" in output
    assert "[hayward] city_finish" in output
    assert "'catalogs_with_summary': 1" in output
    assert "'missing_summary_total': -1" in output
    db_session.expire_all()
    assert db_session.query(Catalog).filter(Catalog.summary.isnot(None)).count() == 5


def test_staged_hydration_json_mode_preserves_cli_controls(
    mocker,
    capsys,
    db_session,
    shared_engine,
):
    _seed_catalogs(db_session, city="berkeley", catalog_count=1)
    _install_summary_boundaries(mocker, shared_engine)
    mocker.patch.object(
        sys,
        "argv",
        [
            "staged_hydrate_cities.py",
            "--city",
            "berkeley",
            "--limit",
            "2",
            "--segment-limit",
            "1",
            "--summary-limit",
            "1",
            "--segment-workers",
            "1",
            "--segment-mode",
            "maintenance",
            "--agenda-timeout-seconds",
            "10",
            "--summary-timeout-seconds",
            "20",
            "--summary-fallback-mode",
            "deterministic",
            "--resume-after-id",
            "0",
            "--max-chunks",
            "1",
            "--force",
            "--json",
        ],
    )

    exit_code = staged_hydrate_cities.main()

    payload = json.loads(capsys.readouterr().out)
    city_payload = payload["cities"][0]
    assert exit_code == 0
    assert city_payload["city"] == "berkeley"
    assert [chunk["chunk_index"] for chunk in city_payload["chunks"]] == [1]
    assert city_payload["summary"]["selected"] == 1
    assert city_payload["summary"]["complete"] == 1
    assert city_payload["delta"]["missing_summary_total"] == -1


def test_hydration_delta_includes_unresolved_segmentation_status_counts():
    delta = staged_hydration_runner.hydration_delta(
        _snapshot(
            missing_summary_total=10,
            catalogs_with_summary=1,
            agenda_missing_summary_total=10,
            agenda_missing_summary_with_items=2,
            agenda_missing_summary_without_items=8,
            non_agenda_missing_summary_total=0,
            agenda_unresolved_segmentation_status_counts={"<null>": 7, "empty": 1},
        ),
        _snapshot(
            missing_summary_total=8,
            catalogs_with_summary=3,
            agenda_missing_summary_total=8,
            agenda_missing_summary_with_items=3,
            agenda_missing_summary_without_items=5,
            non_agenda_missing_summary_total=0,
            agenda_unresolved_segmentation_status_counts={
                "<null>": 5,
                "empty": 2,
                "complete": 1,
            },
        ),
    )

    assert delta["catalogs_with_summary"] == 2
    assert delta["agenda_unresolved_segmentation_status_counts"] == {
        "<null>": -2,
        "complete": 1,
        "empty": 1,
    }


def test_repeat_until_idle_runs_again_then_stops(
    mocker,
    capsys,
    db_session,
    shared_engine,
):
    _seed_catalogs(db_session, city="berkeley", catalog_count=1)
    _install_summary_boundaries(mocker, shared_engine)
    sleep_spy = mocker.patch.object(staged_hydration_runner.time, "sleep")
    mocker.patch.object(
        sys,
        "argv",
        [
            "staged_hydrate_cities.py",
            "--city",
            "berkeley",
            "--repeat-until-idle",
            "--sleep-seconds",
            "1",
            "--json",
        ],
    )

    exit_code = staged_hydrate_cities.main()

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert len(payload["runs"]) == 2
    assert payload["runs"][0]["any_work_done"] is True
    assert payload["runs"][1]["any_work_done"] is False
    assert payload["cities"][0]["summary"]["selected"] == 0
    sleep_spy.assert_called_once_with(1)


def test_real_child_process_preserves_resume_and_multi_chunk_progress(tmp_path):
    database_url, catalog_ids = _seed_file_agenda_database(tmp_path / "staged-hydration.db")
    child_environment = os.environ.copy()
    child_environment.update(
        {
            "DATABASE_URL": database_url,
            "CELERY_BROKER_URL": "memory://",
            "MEILI_HOST": "http://127.0.0.1:1",
        }
    )

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/staged_hydrate_cities.py",
            "--city",
            "berkeley",
            "--segment-limit",
            "1",
            "--segment-workers",
            "1",
            "--segment-mode",
            "maintenance",
            "--resume-after-id",
            str(catalog_ids[0]),
            "--max-chunks",
            "2",
        ],
        check=True,
        capture_output=True,
        cwd=Path.cwd(),
        env=child_environment,
        text=True,
        timeout=60,
    )

    assert f"segmentation_start chunk=1 catalog_count=1" in completed.stdout
    assert f"resume_after_id={catalog_ids[0]}" in completed.stdout
    assert "segmentation_catalog_finish chunk=1 index=1/1" in completed.stdout
    assert f"segmentation_start chunk=2 catalog_count=1" in completed.stdout
    assert f"resume_after_id={catalog_ids[1]}" in completed.stdout
    assert "chunks: 2" in completed.stdout
    assert "'catalog_count': 2" in completed.stdout

    engine = create_engine(database_url)
    with sessionmaker(bind=engine)() as session:
        statuses = {
            catalog.id: catalog.agenda_segmentation_status
            for catalog in session.query(Catalog).order_by(Catalog.id)
        }
    engine.dispose()
    assert statuses == {
        catalog_ids[0]: None,
        catalog_ids[1]: "complete",
        catalog_ids[2]: "complete",
    }


def test_staged_hydration_implementation_modules_do_not_import_entrypoint():
    module_paths = [
        Path("scripts/hydration_counts.py"),
        Path("scripts/hydration_output.py"),
        Path("scripts/staged_hydration_output.py"),
        Path("scripts/staged_hydration_runner.py"),
        Path("scripts/staged_hydration_segment.py"),
    ]

    for module_path in module_paths:
        assert "scripts.staged_hydrate_cities" not in module_path.read_text(encoding="utf-8")

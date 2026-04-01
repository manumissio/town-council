import sys
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError

from pipeline import run_pipeline
from pipeline import run_batch_enrichment
from pipeline.models import Base, Catalog, Document, Event, Place, UrlStage, UrlStageHist


def test_run_step_exits_on_subprocess_failure(mocker):
    mocker.patch("subprocess.run", side_effect=run_pipeline.subprocess.CalledProcessError(1, ["cmd"]))
    with pytest.raises(SystemExit):
        run_pipeline.run_step("bad", ["cmd"])


def test_process_document_chunk_returns_zero_when_db_unavailable(mocker):
    mocker.patch.dict(sys.modules, {"pipeline.extractor": MagicMock()})
    mocker.patch("pipeline.models.db_connect", side_effect=SQLAlchemyError("db down"))
    sleep_spy = mocker.patch("time.sleep")

    processed = run_pipeline.process_document_chunk([1, 2])

    assert processed == 0
    assert sleep_spy.call_count == 3


def test_run_parallel_processing_returns_when_no_unprocessed_docs(mocker):
    selector = mocker.patch("pipeline.run_pipeline.select_catalog_ids_for_processing", return_value=[])
    executor_spy = mocker.patch("pipeline.run_pipeline.ProcessPoolExecutor")

    run_pipeline.run_parallel_processing()

    selector.assert_called_once()
    executor_spy.assert_not_called()


def test_main_runs_steps_in_expected_order(mocker):
    calls = []
    mocker.patch("pipeline.run_pipeline.run_parallel_processing", side_effect=lambda: calls.append("parallel"))

    def fake_run_step(name, command):
        calls.append((name, tuple(command)))

    mocker.patch("pipeline.run_pipeline.run_step", side_effect=fake_run_step)

    run_pipeline.main()

    assert calls[0][0] == "DB Migrate"
    assert calls[1][0] == "Seed Places"
    assert calls[2][0] == "Promote Staged Events"
    assert calls[3][0] == "Downloader"
    assert calls[4] == "parallel"
    assert calls[5][0] == "Agenda Segmentation"
    assert calls[6][0] == "Summary Hydration"
    assert calls[-1][0] == "Summary Hydration"
    assert ("Search Indexing", ("python", "indexer.py")) not in calls
    assert ("Table Extraction", ("python", "table_worker.py")) not in calls
    assert ("Topic Modeling", ("python", "topic_worker.py")) not in calls


def test_main_skips_non_gating_steps_in_onboarding_fast_profile(mocker):
    calls = []
    mocker.patch("pipeline.run_pipeline.run_parallel_processing", side_effect=lambda: calls.append("parallel"))

    def fake_run_step(name, command):
        calls.append((name, tuple(command)))

    mocker.patch("pipeline.run_pipeline.run_step", side_effect=fake_run_step)
    mocker.patch.object(run_pipeline, "PIPELINE_ONBOARDING_CITY", "san_leandro")
    mocker.patch.object(run_pipeline, "PIPELINE_RUNTIME_PROFILE", "onboarding_fast")

    run_pipeline.main()

    assert ("Agenda Segmentation", ("python", "../scripts/backfill_agenda_segmentation.py")) in calls
    assert ("Summary Hydration", ("python", "../scripts/backfill_summaries.py")) in calls
    assert ("Search Indexing", ("python", "indexer.py")) not in calls
    assert ("Table Extraction", ("python", "table_worker.py")) not in calls
    assert ("Backfill Organizations", ("python", "backfill_orgs.py")) not in calls
    assert ("Topic Modeling", ("python", "topic_worker.py")) not in calls
    assert ("People Linking", ("python", "person_linker.py")) not in calls


def test_run_batch_enrichment_runs_heavy_steps_in_expected_order(mocker):
    calls = []

    def fake_run_step(name, command):
        calls.append((name, tuple(command)))

    mocker.patch("pipeline.run_batch_enrichment.run_step", side_effect=fake_run_step)

    run_batch_enrichment.main()

    assert calls == [
        ("Entity Backfill", ("python", "backfill_entities.py")),
        ("Table Extraction", ("python", "table_worker.py")),
        ("Backfill Organizations", ("python", "backfill_orgs.py")),
        ("Topic Modeling", ("python", "topic_worker.py")),
        ("People Linking", ("python", "person_linker.py")),
    ]


def test_run_batch_enrichment_help_exits_before_work(mocker):
    run_step_spy = mocker.patch("pipeline.run_batch_enrichment.run_step")

    with pytest.raises(SystemExit) as excinfo:
        run_batch_enrichment.main(["--help"])

    assert excinfo.value.code == 0
    run_step_spy.assert_not_called()


def test_process_document_chunk_returns_count_for_missing_rows(mocker):
    db = MagicMock()
    db.get.side_effect = [None]
    db.execute.return_value = None
    mocker.patch("pipeline.models.db_connect")
    mocker.patch("sqlalchemy.orm.sessionmaker", return_value=lambda: db)
    mocker.patch.dict(sys.modules, {"pipeline.extractor": MagicMock()})

    count = run_pipeline.process_document_chunk([999])

    assert count == 0
    db.close.assert_called_once()


def test_select_catalog_ids_for_processing_scopes_onboarding_city_and_run_window(mocker):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    san_mateo = Place(
        name="san mateo",
        state="CA",
        ocd_division_id="ocd-division/country:us/state:ca/place:san_mateo",
        crawler_name="san_mateo",
    )
    hayward = Place(
        name="hayward",
        state="CA",
        ocd_division_id="ocd-division/country:us/state:ca/place:hayward",
        crawler_name="hayward",
    )
    db.add_all([san_mateo, hayward])
    db.flush()

    san_event = Event(place_id=san_mateo.id, ocd_division_id=san_mateo.ocd_division_id, name="San Mateo Council")
    hay_event = Event(place_id=hayward.id, ocd_division_id=hayward.ocd_division_id, name="Hayward Council")
    db.add_all([san_event, hay_event])
    db.flush()

    matching_catalog = Catalog(url_hash="match", location="/tmp/match.pdf", content=None, entities=None, extraction_status="pending")
    old_catalog = Catalog(url_hash="old", location="/tmp/old.pdf", content=None, entities=None, extraction_status="pending")
    other_city_catalog = Catalog(url_hash="other", location="/tmp/other.pdf", content=None, entities=None, extraction_status="pending")
    done_catalog = Catalog(url_hash="done", location="/tmp/done.pdf", content="done", entities={"ok": True}, extraction_status="complete")
    db.add_all([matching_catalog, old_catalog, other_city_catalog, done_catalog])
    db.flush()

    db.add_all(
        [
            Document(
                place_id=san_mateo.id,
                event_id=san_event.id,
                catalog_id=matching_catalog.id,
                url="https://example.com/match",
                created_at=run_pipeline.datetime(2026, 3, 13, 23, 0, 0),
            ),
            Document(
                place_id=san_mateo.id,
                event_id=san_event.id,
                catalog_id=old_catalog.id,
                url="https://example.com/old",
                created_at=run_pipeline.datetime(2026, 3, 13, 23, 5, 0),
            ),
            Document(
                place_id=hayward.id,
                event_id=hay_event.id,
                catalog_id=other_city_catalog.id,
                url="https://example.com/other",
                created_at=run_pipeline.datetime(2026, 3, 14, 0, 10, 0),
            ),
            Document(
                place_id=san_mateo.id,
                event_id=san_event.id,
                catalog_id=done_catalog.id,
                url="https://example.com/done",
                created_at=run_pipeline.datetime(2026, 3, 13, 23, 10, 0),
            ),
        ]
    )
    db.add_all(
        [
            UrlStageHist(
                ocd_division_id=san_mateo.ocd_division_id,
                event="San Mateo Council",
                event_date=run_pipeline.datetime(2026, 3, 14, 0, 0, 0).date(),
                url="https://example.com/match",
                url_hash="match",
                category="agenda",
                created_at=run_pipeline.datetime(2026, 3, 14, 0, 5, 0),
            ),
            UrlStageHist(
                ocd_division_id=san_mateo.ocd_division_id,
                event="San Mateo Council",
                event_date=run_pipeline.datetime(2026, 3, 14, 0, 0, 0).date(),
                url="https://example.com/old",
                url_hash="old",
                category="agenda",
                created_at=run_pipeline.datetime(2026, 3, 14, 0, 6, 0),
            ),
            UrlStageHist(
                ocd_division_id=hayward.ocd_division_id,
                event="Hayward Council",
                event_date=run_pipeline.datetime(2026, 3, 14, 0, 0, 0).date(),
                url="https://example.com/other",
                url_hash="other",
                category="agenda",
                created_at=run_pipeline.datetime(2026, 3, 14, 0, 7, 0),
            ),
            UrlStageHist(
                ocd_division_id=san_mateo.ocd_division_id,
                event="San Mateo Council",
                event_date=run_pipeline.datetime(2026, 3, 14, 0, 0, 0).date(),
                url="https://example.com/match",
                url_hash="match",
                category="agenda",
                created_at=run_pipeline.datetime(2026, 3, 14, 0, 8, 0),
            ),
            UrlStageHist(
                ocd_division_id=san_mateo.ocd_division_id,
                event="San Mateo Council",
                event_date=run_pipeline.datetime(2026, 3, 14, 0, 0, 0).date(),
                url="https://example.com/done",
                url_hash="done",
                category="agenda",
                created_at=run_pipeline.datetime(2026, 3, 14, 0, 9, 0),
            ),
        ]
    )
    db.commit()

    mocker.patch.object(run_pipeline, "PIPELINE_ONBOARDING_CITY", "san_mateo")
    mocker.patch.object(run_pipeline, "PIPELINE_ONBOARDING_STARTED_AT_UTC", "2026-03-14T00:00:00Z")

    try:
        ids = run_pipeline.select_catalog_ids_for_processing(db)
        assert ids == [matching_catalog.id, old_catalog.id]
    finally:
        db.close()
        engine.dispose()


def test_select_catalog_ids_for_processing_falls_back_to_live_url_stage(mocker):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    place = Place(
        name="san mateo",
        state="CA",
        ocd_division_id="ocd-division/country:us/state:ca/place:san_mateo",
        crawler_name="san mateo",
    )
    event = Event(place=place, ocd_division_id=place.ocd_division_id, name="San Mateo Council")
    catalog = Catalog(url_hash="live-hash", location="/tmp/live.pdf", content=None, entities=None, extraction_status="pending")
    db.add_all([place, event, catalog])
    db.flush()
    db.add(
        Document(
            place_id=place.id,
            event_id=event.id,
            catalog_id=catalog.id,
            url="https://example.com/live",
            created_at=run_pipeline.datetime(2026, 3, 13, 23, 0, 0),
        )
    )
    db.add(
        UrlStage(
            ocd_division_id=place.ocd_division_id,
            event=event.name,
            event_date=run_pipeline.datetime(2026, 3, 14, 0, 0, 0).date(),
            url="https://example.com/live",
            url_hash="live-hash",
            category="agenda",
            created_at=run_pipeline.datetime(2026, 3, 14, 0, 5, 0),
        )
    )
    db.commit()

    mocker.patch.object(run_pipeline, "PIPELINE_ONBOARDING_CITY", "san_mateo")
    mocker.patch.object(run_pipeline, "PIPELINE_ONBOARDING_STARTED_AT_UTC", "2026-03-14T00:00:00Z")

    try:
        ids = run_pipeline.select_catalog_ids_for_processing(db)
        assert ids == [catalog.id]
    finally:
        db.close()
        engine.dispose()


def test_select_catalog_ids_for_processing_keeps_extraction_rows_and_skips_terminal_failures(mocker):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    extraction_needed = Catalog(
        url_hash="extract-me",
        location="/tmp/extract.pdf",
        content=None,
        entities=None,
        extraction_status="pending",
    )
    terminal = Catalog(
        url_hash="failed",
        location="/tmp/failed.pdf",
        content=None,
        entities=None,
        extraction_status="failed_terminal",
    )
    db.add_all([extraction_needed, terminal])
    db.commit()

    try:
        ids = run_pipeline.select_catalog_ids_for_processing(db)
        assert ids == [extraction_needed.id]
    finally:
        db.close()
        engine.dispose()


def test_catalog_entities_need_nlp_uses_postgres_safe_json_null_check():
    expr = run_pipeline._catalog_entities_need_nlp(Catalog)
    compiled = str(expr.compile(dialect=postgresql.dialect()))

    assert "catalog.entities IS NULL" in compiled
    assert "CAST(catalog.entities AS TEXT) = %(param_1)s" in compiled


def test_select_catalog_ids_for_entity_backfill_keeps_json_null_rows(mocker):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    nlp_json_null = Catalog(
        url_hash="nlp-json-null",
        location="/tmp/nlp-json-null.pdf",
        content="ready",
        entities={"placeholder": True},
        extraction_status="complete",
    )
    done_catalog = Catalog(
        url_hash="done-json",
        location="/tmp/done-json.pdf",
        content="done",
        entities={"ok": True},
        extraction_status="complete",
    )
    db.add_all([nlp_json_null, done_catalog])
    db.commit()
    db.execute(text("UPDATE catalog SET entities = 'null' WHERE id = :catalog_id"), {"catalog_id": nlp_json_null.id})
    db.commit()

    try:
        ids = run_pipeline.select_catalog_ids_for_entity_backfill(db)
        assert ids == [nlp_json_null.id]
    finally:
        db.close()
        engine.dispose()


def test_select_catalog_ids_for_entity_backfill_keeps_nlp_only_rows(mocker):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    needs_entities = Catalog(
        url_hash="needs-entities",
        location="/tmp/entities.pdf",
        content="ready",
        entities=None,
        extraction_status="complete",
    )
    done_catalog = Catalog(
        url_hash="done",
        location="/tmp/done.pdf",
        content="done",
        entities={"ok": True},
        extraction_status="complete",
    )
    db.add_all([needs_entities, done_catalog])
    db.commit()

    try:
        ids = run_pipeline.select_catalog_ids_for_entity_backfill(db)
        assert ids == [needs_entities.id]
    finally:
        db.close()
        engine.dispose()

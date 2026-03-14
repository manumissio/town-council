import importlib.util
import sys
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from pipeline.models import Base, Catalog, Document, Event, Place, UrlStage, UrlStageHist


spec = importlib.util.spec_from_file_location(
    "evaluate_city_onboarding", Path("scripts/evaluate_city_onboarding.py")
)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def test_gate_evaluator_pass_thresholds():
    metrics = mod.CityMetrics(
        run_count=3,
        crawl_success_count=3,
        search_success_count=3,
        catalog_total=20,
        agenda_catalog_total=10,
        extraction_non_empty_count=19,
        segmentation_complete_empty_count=10,
        segmentation_failed_count=0,
        run_window_catalog_total=10,
        run_window_agenda_catalog_total=10,
        run_window_extraction_non_empty_count=10,
        run_window_segmentation_complete_empty_count=10,
        run_window_segmentation_failed_count=0,
    )
    result = mod._evaluate_city("hayward", metrics)

    assert result["quality_gate"] == "pass"
    assert result["failed_gates"] == []


def test_gate_evaluator_fail_thresholds():
    metrics = mod.CityMetrics(
        run_count=3,
        crawl_success_count=2,
        search_success_count=2,
        catalog_total=200,
        agenda_catalog_total=100,
        extraction_non_empty_count=180,
        segmentation_complete_empty_count=98,
        segmentation_failed_count=2,
        run_window_catalog_total=20,
        run_window_agenda_catalog_total=10,
        run_window_extraction_non_empty_count=10,
        run_window_segmentation_complete_empty_count=8,
        run_window_segmentation_failed_count=2,
    )
    result = mod._evaluate_city("san_mateo", metrics)

    assert result["quality_gate"] == "fail"
    assert "crawl_success_rate_gte_95pct" in result["failed_gates"]
    assert "non_empty_extraction_rate_gte_90pct" in result["failed_gates"]
    assert "searchability_smoke_pass" in result["failed_gates"]


def test_gate_evaluator_marks_insufficient_data():
    metrics = mod.CityMetrics(
        run_count=3,
        crawl_success_count=3,
        search_success_count=3,
        catalog_total=100,
        agenda_catalog_total=80,
        extraction_non_empty_count=90,
        segmentation_complete_empty_count=79,
        segmentation_failed_count=1,
        run_window_catalog_total=0,
        run_window_agenda_catalog_total=0,
        run_window_extraction_non_empty_count=0,
        run_window_segmentation_complete_empty_count=0,
        run_window_segmentation_failed_count=0,
    )
    result = mod._evaluate_city("hayward", metrics)

    assert result["quality_gate"] == "insufficient_data"


def test_collect_city_metrics_uses_run_window_touched_catalogs_for_denominator():
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
    db.add(place)
    db.flush()

    event = Event(
        place_id=place.id,
        ocd_division_id=place.ocd_division_id,
        name="San Mateo Council",
        source="san mateo",
        scraped_datetime=mod.datetime(2026, 3, 10, 10, 0, 0),
    )
    db.add(event)
    db.flush()

    historical_catalog = Catalog(url_hash="historical", location="/tmp/historical.pdf", content=None, entities=None)
    touched_catalog = Catalog(url_hash="touched", location="/tmp/touched.pdf", content="extracted", entities=None)
    touched_catalog_2 = Catalog(url_hash="touched-2", location="/tmp/touched-2.pdf", content="extracted", entities=None)
    db.add_all([historical_catalog, touched_catalog, touched_catalog_2])
    db.flush()

    db.add_all(
        [
            Document(
                place_id=place.id,
                event_id=event.id,
                catalog_id=historical_catalog.id,
                url="https://example.com/historical",
                url_hash="historical",
                category="agenda",
            ),
            Document(
                place_id=place.id,
                event_id=event.id,
                catalog_id=touched_catalog.id,
                url="https://example.com/touched",
                url_hash="touched",
                category="agenda",
            ),
            Document(
                place_id=place.id,
                event_id=event.id,
                catalog_id=touched_catalog_2.id,
                url="https://example.com/touched-2",
                url_hash="touched-2",
                category="agenda",
            ),
        ]
    )
    db.add_all(
        [
            UrlStageHist(
                ocd_division_id=place.ocd_division_id,
                event=event.name,
                event_date=mod.datetime(2026, 3, 14, 0, 0, 0).date(),
                url="https://example.com/touched",
                url_hash="touched",
                category="agenda",
                created_at=mod.datetime(2026, 3, 14, 0, 5, 0),
            ),
            UrlStageHist(
                ocd_division_id=place.ocd_division_id,
                event=event.name,
                event_date=mod.datetime(2026, 3, 14, 0, 0, 0).date(),
                url="https://example.com/touched",
                url_hash="touched",
                category="agenda",
                created_at=mod.datetime(2026, 3, 14, 0, 6, 0),
            ),
            UrlStageHist(
                ocd_division_id=place.ocd_division_id,
                event=event.name,
                event_date=mod.datetime(2026, 3, 14, 0, 0, 0).date(),
                url="https://example.com/touched-2",
                url_hash="touched-2",
                category="agenda",
                created_at=mod.datetime(2026, 3, 14, 0, 7, 0),
            ),
        ]
    )
    db.commit()

    city_runs = [
        {
            "started_dt": mod._parse_iso_utc("2026-03-14T00:00:00Z"),
            "finished_dt": mod._parse_iso_utc("2026-03-14T01:00:00Z"),
            "crawler_status": "success",
            "search_status": "success",
        }
    ]

    try:
        metrics = mod._collect_city_metrics(db, "san_mateo", city_runs)
        assert metrics.catalog_total == 3
        assert metrics.agenda_catalog_total == 3
        assert metrics.run_window_catalog_total == 2
        assert metrics.run_window_agenda_catalog_total == 2
        assert metrics.run_window_extraction_non_empty_count == 2
        assert metrics.run_window_segmentation_complete_empty_count == 0
    finally:
        db.close()
        engine.dispose()


def test_collect_city_metrics_falls_back_to_live_url_stage_before_archive():
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
    db.add(place)
    db.flush()

    event = Event(
        place_id=place.id,
        ocd_division_id=place.ocd_division_id,
        name="San Mateo Council",
        source="san_mateo",
        scraped_datetime=mod.datetime(2026, 3, 14, 0, 10, 0),
    )
    db.add(event)
    db.flush()

    catalog = Catalog(
        url_hash="live-hash",
        location="/tmp/live.pdf",
        content="ready",
        entities={"ok": True},
        agenda_segmentation_status="complete",
    )
    db.add(catalog)
    db.flush()

    db.add(
        Document(
            place_id=place.id,
            event_id=event.id,
            catalog_id=catalog.id,
            url="https://example.com/live",
            url_hash="live-hash",
            category="agenda",
        )
    )
    db.add(
        UrlStage(
            ocd_division_id=place.ocd_division_id,
            event=event.name,
            event_date=mod.datetime(2026, 3, 14, 0, 0, 0).date(),
            url="https://example.com/live",
            url_hash="live-hash",
            category="agenda",
            created_at=mod.datetime(2026, 3, 14, 0, 5, 0),
        )
    )
    db.commit()

    city_runs = [
        {
            "started_dt": mod._parse_iso_utc("2026-03-14T00:00:00Z"),
            "finished_dt": mod._parse_iso_utc("2026-03-14T01:00:00Z"),
            "crawler_status": "success",
            "search_status": "success",
        }
    ]

    try:
        metrics = mod._collect_city_metrics(db, "san_mateo", city_runs)
        assert metrics.run_window_catalog_total == 1
        assert metrics.run_window_agenda_catalog_total == 1
        assert metrics.run_window_extraction_non_empty_count == 1
        assert metrics.run_window_segmentation_complete_empty_count == 1
    finally:
        db.close()
        engine.dispose()


def test_collect_city_metrics_returns_insufficient_run_window_when_touched_hashes_do_not_resolve():
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
    db.add(place)
    db.flush()

    db.add(
        UrlStageHist(
            ocd_division_id=place.ocd_division_id,
            event="San Mateo Council",
            event_date=mod.datetime(2026, 3, 14, 0, 0, 0).date(),
            url="https://example.com/missing",
            url_hash="missing",
            category="agenda",
            created_at=mod.datetime(2026, 3, 14, 0, 5, 0),
        )
    )
    db.commit()

    city_runs = [
        {
            "started_dt": mod._parse_iso_utc("2026-03-14T00:00:00Z"),
            "finished_dt": mod._parse_iso_utc("2026-03-14T01:00:00Z"),
            "crawler_status": "success",
            "search_status": "success",
        }
    ]

    try:
        metrics = mod._collect_city_metrics(db, "san_mateo", city_runs)
        result = mod._evaluate_city("san_mateo", metrics)
        assert metrics.run_window_catalog_total == 0
        assert result["quality_gate"] == "insufficient_data"
    finally:
        db.close()
        engine.dispose()


def test_source_aliases_for_city_include_legacy_spaced_name():
    assert mod._source_aliases_for_city("san_mateo") == {"san_mateo", "san mateo"}

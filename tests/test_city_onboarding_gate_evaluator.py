import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock


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
    )
    result = mod._evaluate_city("hayward", metrics)

    assert result["quality_gate"] == "pass"
    assert result["failed_gates"] == []


def test_gate_evaluator_fail_thresholds():
    metrics = mod.CityMetrics(
        run_count=3,
        crawl_success_count=2,
        search_success_count=2,
        catalog_total=20,
        agenda_catalog_total=10,
        extraction_non_empty_count=10,
        segmentation_complete_empty_count=8,
        segmentation_failed_count=2,
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
        catalog_total=0,
        agenda_catalog_total=0,
        extraction_non_empty_count=0,
        segmentation_complete_empty_count=0,
        segmentation_failed_count=0,
    )
    result = mod._evaluate_city("hayward", metrics)

    assert result["quality_gate"] == "insufficient_data"


def test_collect_city_metrics_falls_back_to_city_corpus_when_window_empty():
    session = MagicMock()

    q_window = MagicMock()
    q_fallback = MagicMock()
    q_catalog = MagicMock()
    session.query.side_effect = [q_window, q_fallback, q_catalog]

    q_window.filter.return_value.filter.return_value.all.return_value = []
    q_fallback.filter.return_value.all.return_value = [(101,), (102,)]
    q_catalog.join.return_value.filter.return_value.all.return_value = [
        ("agenda", "some extracted text", "complete"),
        ("minutes", "", "failed"),
    ]

    city_runs = [
        {
            "started_dt": mod._parse_iso_utc("2026-03-06T03:00:00Z"),
            "finished_dt": mod._parse_iso_utc("2026-03-06T03:30:00Z"),
            "crawler_status": "success",
            "search_status": "success",
        }
    ]

    metrics = mod._collect_city_metrics(session, "hayward", city_runs)

    assert metrics.catalog_total == 2
    assert metrics.agenda_catalog_total == 1
    assert metrics.extraction_non_empty_count == 1
    assert metrics.segmentation_complete_empty_count == 1
    assert metrics.segmentation_failed_count == 0


def test_source_aliases_for_city_include_legacy_spaced_name():
    assert mod._source_aliases_for_city("san_mateo") == {"san_mateo", "san mateo"}

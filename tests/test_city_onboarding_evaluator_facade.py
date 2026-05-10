import importlib.util
import json
import sys
from pathlib import Path


spec = importlib.util.spec_from_file_location(
    "evaluate_city_onboarding_facade", Path("scripts/evaluate_city_onboarding.py")
)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def test_evaluator_facade_reexports_legacy_helpers_and_models():
    from pipeline import city_onboarding_metrics
    from pipeline import models

    assert mod.ISO_FMT == city_onboarding_metrics.ISO_FMT
    assert mod._ocd_division_id_for_city is city_onboarding_metrics.ocd_division_id_for_city
    assert mod._build_counts is city_onboarding_metrics.build_counts
    assert mod.Catalog is models.Catalog
    assert mod.Document is models.Document
    assert mod.Event is models.Event
    assert mod.UrlStage is models.UrlStage
    assert mod.UrlStageHist is models.UrlStageHist


def test_evaluator_facade_writes_artifacts_and_stdout(tmp_path, monkeypatch, capsys):
    run_id = "facade_contract"
    run_dir = tmp_path / run_id
    run_dir.mkdir()
    (run_dir / "runs.jsonl").write_text(
        json.dumps(
            {
                "city": "hayward",
                "started_at_utc": "2026-03-14T00:00:00Z",
                "finished_at_utc": "2026-03-14T01:00:00Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    expected_result = {
        "city": "hayward",
        "quality_gate": "pass",
        "quality_gate_reason": "fresh_evidence",
        "run_window_catalog_total": 1,
        "catalog_total": 1,
        "crawl_success_rate": 1.0,
        "extraction_non_empty_rate": 1.0,
        "segmentation_complete_empty_rate": 1.0,
        "segmentation_failed_rate": 0.0,
        "failed_gates": [],
    }

    monkeypatch.setattr(mod, "_load_city_metadata_slugs", lambda: {"hayward"})
    monkeypatch.setattr(mod, "_evaluate_selected_cities", lambda rows, cities: [expected_result])
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "evaluate_city_onboarding.py",
            "--run-id",
            run_id,
            "--cities",
            "hayward",
            "--output-dir",
            str(tmp_path),
        ],
    )

    assert mod.main() == 0

    output_json = run_dir / "city_gate_eval.json"
    output_md = run_dir / "city_gate_eval.md"
    assert json.loads(output_json.read_text(encoding="utf-8")) == {
        "run_id": run_id,
        "results": [expected_result],
    }
    assert "hayward | pass | fresh_evidence" in output_md.read_text(encoding="utf-8")
    assert capsys.readouterr().out == f"wrote: {output_json}\nwrote: {output_md}\n"

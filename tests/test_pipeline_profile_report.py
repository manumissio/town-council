import importlib.util
import json
from pathlib import Path


spec = importlib.util.spec_from_file_location("analyze_pipeline_profile", Path("scripts/analyze_pipeline_profile.py"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_rank_bottlenecks_prefers_longest_leaf_phase(tmp_path: Path):
    run_dir = tmp_path / "profile_run"
    run_dir.mkdir()
    (run_dir / "run_manifest.json").write_text(
        json.dumps({"run_id": "profile_run", "mode": "triage", "catalog_count": 10, "baseline_valid": False}),
        encoding="utf-8",
    )
    (run_dir / "result.json").write_text(json.dumps({"elapsed_seconds": 100.0}), encoding="utf-8")
    (run_dir / "day_summary.json").write_text(json.dumps({"provider_metrics_present": True}), encoding="utf-8")
    (run_dir / "worker_metrics.prom").write_text(
        'tc_provider_requests_total{provider="http",operation="summarize_text",model="m",outcome="ok"} 4\n',
        encoding="utf-8",
    )
    (run_dir / "spans.jsonl").write_text(
        "\n".join(
            [
                json.dumps({"event_type": "span", "phase": "download", "duration_s": 5.0}),
                json.dumps({"event_type": "span", "phase": "summarize", "duration_s": 22.0}),
                json.dumps({"event_type": "task_span", "phase": "summarize", "duration_s": 18.0, "queue_wait_s": 7.0}),
                json.dumps({"event_type": "span", "phase": "table_extraction", "duration_s": 9.0}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    summary = mod.rank_bottlenecks(run_dir)

    assert summary["top_bottlenecks"][0]["phase"] == "summarize"
    assert summary["top_bottlenecks"][0]["classification"] in {"queueing", "inference/provider"}


def test_rank_bottlenecks_uses_combined_total_for_repeated_phases(tmp_path: Path):
    run_dir = tmp_path / "profile_run_combined"
    run_dir.mkdir()
    (run_dir / "run_manifest.json").write_text(
        json.dumps({"run_id": "profile_run_combined", "mode": "triage", "catalog_count": 25, "baseline_valid": False, "include_batch": True}),
        encoding="utf-8",
    )
    (run_dir / "result.json").write_text(
        json.dumps(
            {
                "elapsed_seconds": 47.2,
                "totals": {
                    "core_elapsed_seconds": 23.0,
                    "batch_elapsed_seconds": 24.2,
                    "combined_elapsed_seconds": 47.2,
                },
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "day_summary.json").write_text(json.dumps({"provider_metrics_present": True}), encoding="utf-8")
    (run_dir / "worker_metrics.prom").write_text("", encoding="utf-8")
    (run_dir / "spans.jsonl").write_text(
        "\n".join(
            [
                json.dumps({"event_type": "span", "phase": "pipeline_total", "duration_s": 23.0}),
                json.dumps({"event_type": "span", "phase": "batch_enrichment_total", "duration_s": 24.2}),
                json.dumps({"event_type": "span", "phase": "index_search", "component": "subprocess", "duration_s": 18.8}),
                json.dumps({"event_type": "span", "phase": "index_search", "component": "subprocess", "duration_s": 19.3}),
                json.dumps({"event_type": "span", "phase": "entity_backfill", "component": "subprocess", "duration_s": 2.1}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    summary = mod.rank_bottlenecks(run_dir)

    top = summary["top_bottlenecks"][0]
    assert summary["confidence"] == "ok"
    assert summary["elapsed_source"] == "result_totals"
    assert top["phase"] == "index_search"
    assert top["occurrence_count"] == 2
    assert top["contribution_pct"] < 100.0


def test_rank_bottlenecks_marks_missing_result_as_reduced_confidence(tmp_path: Path):
    run_dir = tmp_path / "profile_run_missing_result"
    run_dir.mkdir()
    (run_dir / "run_manifest.json").write_text(
        json.dumps({"run_id": "profile_run_missing_result", "mode": "triage", "catalog_count": 25, "baseline_valid": False}),
        encoding="utf-8",
    )
    (run_dir / "day_summary.json").write_text(json.dumps({"provider_metrics_present": True}), encoding="utf-8")
    (run_dir / "spans.jsonl").write_text(
        "\n".join(
            [
                json.dumps({"event_type": "span", "phase": "pipeline_total", "duration_s": 20.0}),
                json.dumps({"event_type": "span", "phase": "batch_enrichment_total", "duration_s": 10.0}),
                json.dumps({"event_type": "span", "phase": "index_search", "component": "subprocess", "duration_s": 12.0}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    summary = mod.rank_bottlenecks(run_dir)

    assert summary["elapsed_seconds"] == 30.0
    assert summary["confidence"] == "reduced-confidence:result_missing"

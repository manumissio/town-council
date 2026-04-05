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


def test_rank_bottlenecks_classifies_deterministic_summary_runs_without_provider_bias(tmp_path: Path):
    run_dir = tmp_path / "profile_run_deterministic"
    run_dir.mkdir()
    (run_dir / "run_manifest.json").write_text(
        json.dumps({"run_id": "profile_run_deterministic", "mode": "baseline", "catalog_count": 12, "baseline_valid": True}),
        encoding="utf-8",
    )
    (run_dir / "result.json").write_text(
        json.dumps({"totals": {"combined_elapsed_seconds": 10.0}}),
        encoding="utf-8",
    )
    (run_dir / "day_summary.json").write_text(json.dumps({"provider_metrics_present": True}), encoding="utf-8")
    (run_dir / "worker_metrics.prom").write_text(
        'tc_provider_requests_total{provider="http",operation="summarize_text",model="m",outcome="ok"} 4\n',
        encoding="utf-8",
    )
    (run_dir / "commands.log").write_text(
        "2026-04-02 22:05:08,519 - celery-worker - INFO - summary_hydration_backfill selected=12 complete=12 changed_catalogs=12 cached=0 stale=0 blocked_low_signal=0 blocked_ungrounded=0 not_generated_yet=0 error=0 other=0 agenda_deterministic_complete=12 llm_complete=0 deterministic_fallback_complete=0 reindexed=12 reindex_failed=0 embed_enqueued=12 embed_dispatch_failed=0 agenda_summary_bundle_build_ms=125 agenda_summary_render_ms=240 agenda_summary_persist_ms=315 agenda_summary_reindex_ms=410 agenda_summary_embed_dispatch_ms=505\n",
        encoding="utf-8",
    )
    (run_dir / "spans.jsonl").write_text(
        json.dumps({"event_type": "span", "phase": "summarize", "duration_s": 3.6, "component": "pipeline"}) + "\n",
        encoding="utf-8",
    )

    summary = mod.rank_bottlenecks(run_dir)

    top = summary["top_bottlenecks"][0]
    assert top["phase"] == "summarize"
    assert top["classification"] == "CPU/parsing"
    assert top["provider_requests_total"] == 0.0
    assert summary["summarize_subphase_timings_ms"]["agenda_summary_render_ms"] == 240


def test_rank_bottlenecks_defaults_malformed_optional_summary_subphase_counters_to_zero(tmp_path: Path):
    run_dir = tmp_path / "profile_run_bad_subphases"
    run_dir.mkdir()
    (run_dir / "run_manifest.json").write_text(
        json.dumps({"run_id": "profile_run_bad_subphases", "mode": "baseline", "catalog_count": 12, "baseline_valid": True}),
        encoding="utf-8",
    )
    (run_dir / "result.json").write_text(
        json.dumps({"totals": {"combined_elapsed_seconds": 10.0}}),
        encoding="utf-8",
    )
    (run_dir / "day_summary.json").write_text(json.dumps({"provider_metrics_present": True}), encoding="utf-8")
    (run_dir / "worker_metrics.prom").write_text("", encoding="utf-8")
    (run_dir / "commands.log").write_text(
        "2026-04-02 22:05:08,519 - celery-worker - INFO - summary_hydration_backfill selected=12 complete=12 changed_catalogs=12 cached=0 stale=0 blocked_low_signal=0 blocked_ungrounded=0 not_generated_yet=0 error=0 other=0 agenda_deterministic_complete=12 llm_complete=bogus deterministic_fallback_complete=0 reindexed=12 reindex_failed=0 embed_enqueued=12 embed_dispatch_failed=0 agenda_summary_bundle_build_ms=11 agenda_summary_render_ms=oops agenda_summary_persist_ms=33 agenda_summary_reindex_ms= agenda_summary_embed_dispatch_ms=55\n",
        encoding="utf-8",
    )
    (run_dir / "spans.jsonl").write_text(
        json.dumps({"event_type": "span", "phase": "summarize", "duration_s": 3.6, "component": "pipeline"}) + "\n",
        encoding="utf-8",
    )

    summary = mod.rank_bottlenecks(run_dir)

    assert summary["top_bottlenecks"][0]["classification"] == "CPU/parsing"
    assert summary["summarize_subphase_timings_ms"]["agenda_summary_bundle_build_ms"] == 11
    assert summary["summarize_subphase_timings_ms"]["agenda_summary_render_ms"] == 0
    assert summary["summarize_subphase_timings_ms"]["agenda_summary_reindex_ms"] == 0


def test_render_report_includes_summarize_subphase_timings_when_present():
    report = mod.render_report(
        {
            "run_id": "profile_run",
            "mode": "baseline",
            "catalog_count": 12,
            "elapsed_seconds": 9.61,
            "confidence": "ok",
            "top_bottlenecks": [
                {
                    "phase": "summarize",
                    "classification": "CPU/parsing",
                    "duration_s": 3.877,
                    "contribution_pct": 40.34,
                    "queue_wait_s": 0.0,
                    "task_duration_s": 0.0,
                    "occurrence_count": 1,
                }
            ],
            "summarize_subphase_timings_ms": {
                "agenda_summary_bundle_build_ms": 10,
                "agenda_summary_render_ms": 20,
                "agenda_summary_persist_ms": 30,
                "agenda_summary_reindex_ms": 40,
                "agenda_summary_embed_dispatch_ms": 50,
            },
        }
    )

    assert "## Summarize Subphase Timings (ms)" in report
    assert "`agenda_summary_render_ms`: `20`" in report


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


def _write_compare_fixture(run_dir: Path, *, elapsed_seconds: float = 9.473, summarize_duration: float = 3.601, selected: int = 12, confidence_provider: bool = True):
    (run_dir / "run_manifest.json").write_text(
        json.dumps({"run_id": run_dir.name, "mode": "baseline", "catalog_count": 30, "baseline_valid": True}),
        encoding="utf-8",
    )
    (run_dir / "result.json").write_text(
        json.dumps({"totals": {"combined_elapsed_seconds": elapsed_seconds}}),
        encoding="utf-8",
    )
    (run_dir / "day_summary.json").write_text(
        json.dumps({"provider_metrics_present": confidence_provider}),
        encoding="utf-8",
    )
    (run_dir / "worker_metrics.prom").write_text("", encoding="utf-8")
    (run_dir / "commands.log").write_text(
        "\n".join(
            [
                f"2026-04-03 00:41:44,793 - celery-worker - INFO - summary_hydration_backfill selected={selected} complete=12 changed_catalogs=12 cached=0 stale=0 blocked_low_signal=0 blocked_ungrounded=0 not_generated_yet=0 error=0 other=0 agenda_deterministic_complete=12 llm_complete=0 deterministic_fallback_complete=0 reindexed=12 reindex_failed=0 embed_enqueued=12 embed_dispatch_failed=0",
                "2026-04-03 00:41:47,581 - entity-backfill - INFO - entity_backfill selected=8 complete=8 changed_catalogs=8 execution_mode=in_process chunks=1 ner_processed=8 ner_skipped_low_signal=0 freshness_advanced=8 candidate_slice_fallback_prefix=0",
                "2026-04-03 00:41:48,224 - pipeline-batch - INFO - people_linking_preflight selected=8",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (run_dir / "spans.jsonl").write_text(
        "\n".join(
            [
                json.dumps({"event_type": "span", "phase": "summarize", "duration_s": summarize_duration, "component": "pipeline"}),
                json.dumps({"event_type": "span", "phase": "entity_backfill", "duration_s": 1.576, "component": "pipeline-batch"}),
                json.dumps({"event_type": "span", "phase": "people_linking", "duration_s": 0.987, "component": "pipeline-batch"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_compare_against_expected_baseline_passes_for_matching_run(tmp_path: Path):
    run_dir = tmp_path / "profile_run_match"
    run_dir.mkdir()
    _write_compare_fixture(run_dir)

    summary = mod.rank_bottlenecks(run_dir)
    comparison = mod.compare_against_expected_baseline(
        run_dir,
        summary,
        Path("profiling/baselines/baseline_representative_v1.json"),
    )

    assert comparison["status"] == "pass"
    assert comparison["comparable"] is True


def test_compare_against_expected_baseline_fails_for_timing_regression(tmp_path: Path):
    run_dir = tmp_path / "profile_run_slow"
    run_dir.mkdir()
    _write_compare_fixture(run_dir, elapsed_seconds=12.5, summarize_duration=5.0)

    summary = mod.rank_bottlenecks(run_dir)
    comparison = mod.compare_against_expected_baseline(
        run_dir,
        summary,
        Path("profiling/baselines/baseline_representative_v1.json"),
    )

    assert comparison["status"] == "fail"
    assert any(check["metric"] == "elapsed_seconds" and check["status"] == "fail" for check in comparison["checks"])


def test_compare_against_expected_baseline_fails_for_counter_drift(tmp_path: Path):
    run_dir = tmp_path / "profile_run_counter_drift"
    run_dir.mkdir()
    _write_compare_fixture(run_dir, selected=15)

    summary = mod.rank_bottlenecks(run_dir)
    comparison = mod.compare_against_expected_baseline(
        run_dir,
        summary,
        Path("profiling/baselines/baseline_representative_v1.json"),
    )

    assert comparison["status"] == "fail"
    assert any(
        check["metric"] == "summary_hydration_backfill.selected" and check["status"] == "fail"
        for check in comparison["checks"]
    )


def test_compare_against_expected_baseline_marks_reduced_confidence_as_non_comparable(tmp_path: Path):
    run_dir = tmp_path / "profile_run_low_confidence"
    run_dir.mkdir()
    _write_compare_fixture(run_dir, confidence_provider=False)

    summary = mod.rank_bottlenecks(run_dir)
    comparison = mod.compare_against_expected_baseline(
        run_dir,
        summary,
        Path("profiling/baselines/baseline_representative_v1.json"),
    )

    assert comparison["status"] == "non_comparable"
    assert comparison["reason"] == "confidence_reduced"


def test_compare_profile_runs_passes_for_matching_pair(tmp_path: Path):
    control_dir = tmp_path / "control_run"
    treatment_dir = tmp_path / "treatment_run"
    control_dir.mkdir()
    treatment_dir.mkdir()
    _write_compare_fixture(control_dir)
    _write_compare_fixture(treatment_dir, elapsed_seconds=9.8, summarize_duration=3.8)

    control_manifest = json.loads((control_dir / "run_manifest.json").read_text(encoding="utf-8"))
    control_manifest["profile"] = {
        "LOCAL_AI_BACKEND": "http",
        "LOCAL_AI_HTTP_PROFILE": "conservative",
        "LOCAL_AI_HTTP_MODEL": "gemma-3-270m-custom",
        "WORKER_CONCURRENCY": "3",
        "WORKER_POOL": "prefork",
        "OLLAMA_NUM_PARALLEL": "1",
    }
    (control_dir / "run_manifest.json").write_text(json.dumps(control_manifest), encoding="utf-8")

    treatment_manifest = json.loads((treatment_dir / "run_manifest.json").read_text(encoding="utf-8"))
    treatment_manifest["catalog_ids"] = control_manifest.get("catalog_ids")
    treatment_manifest["profile"] = {
        **control_manifest["profile"],
        "LOCAL_AI_HTTP_MODEL": "gemma4:e2b",
    }
    (treatment_dir / "run_manifest.json").write_text(json.dumps(treatment_manifest), encoding="utf-8")
    (control_dir / "day_summary.json").write_text(json.dumps({"provider_metrics_present": True, "provider_requests_delta_run": 10.0}), encoding="utf-8")
    (treatment_dir / "day_summary.json").write_text(json.dumps({"provider_metrics_present": True, "provider_requests_delta_run": 12.0}), encoding="utf-8")

    comparison = mod.compare_profile_runs(control_dir, treatment_dir)

    assert comparison["status"] == "pass"
    assert comparison["control_model"] == "gemma-3-270m-custom"
    assert comparison["treatment_model"] == "gemma4:e2b"


def test_compare_profile_runs_fails_for_profile_drift(tmp_path: Path):
    control_dir = tmp_path / "control_run"
    treatment_dir = tmp_path / "treatment_run"
    control_dir.mkdir()
    treatment_dir.mkdir()
    _write_compare_fixture(control_dir)
    _write_compare_fixture(treatment_dir)
    for run_dir, model in ((control_dir, "gemma-3-270m-custom"), (treatment_dir, "gemma4:e2b")):
        manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
        manifest["profile"] = {
            "LOCAL_AI_BACKEND": "http",
            "LOCAL_AI_HTTP_PROFILE": "conservative" if run_dir == control_dir else "balanced",
            "LOCAL_AI_HTTP_MODEL": model,
            "WORKER_CONCURRENCY": "3",
            "WORKER_POOL": "prefork",
            "OLLAMA_NUM_PARALLEL": "1",
        }
        (run_dir / "run_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        (run_dir / "day_summary.json").write_text(json.dumps({"provider_metrics_present": True}), encoding="utf-8")

    comparison = mod.compare_profile_runs(control_dir, treatment_dir)

    assert comparison["status"] == "fail"
    assert any(check["metric"] == "profile.LOCAL_AI_HTTP_PROFILE" and check["status"] == "fail" for check in comparison["checks"])

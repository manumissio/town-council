import json
from pathlib import Path

from scripts import operator_profile_artifacts as artifacts
from scripts import operator_profile_metrics as metrics
from scripts import operator_profile_reports as reports


def test_profile_artifact_helpers_preserve_result_payload_shape(tmp_path: Path):
    payload = artifacts.build_result_payload(
        run_id="profile_run",
        status="completed",
        started_at="2026-04-01T00:00:00+00:00",
        finished_at="2026-04-01T00:01:00+00:00",
        elapsed_seconds=60.1234,
        include_batch=True,
        segments=[
            {"name": "pipeline", "status": "completed", "elapsed_seconds": 12.3456},
            {"name": "pipeline-batch", "status": "completed", "elapsed_seconds": 7.8912},
        ],
        error_message=None,
        quality={"notes": [], "flags": {}},
    )

    out = tmp_path / "result.json"
    artifacts.write_json(out, payload)

    persisted = json.loads(out.read_text(encoding="utf-8"))
    assert persisted["totals"] == {
        "core_elapsed_seconds": 12.346,
        "batch_elapsed_seconds": 7.891,
        "combined_elapsed_seconds": 20.237,
    }
    assert persisted["profile"]["workload_only"] is True
    assert out.read_text(encoding="utf-8").endswith("\n")


def test_profile_manifest_loader_deduplicates_and_ignores_comments(tmp_path: Path):
    manifest = tmp_path / "catalog_manifest.txt"
    manifest.write_text("11\n12 # keep first\n\n11\n", encoding="utf-8")

    assert artifacts.load_manifest_catalog_ids(manifest) == [11, 12]


def test_profile_metric_helpers_preserve_canonical_run_delta_policy():
    deltas = metrics.provider_run_deltas_from_manifest(
        {
            "provider_counters_before_run": {
                "provider_requests_total": 10.0,
                "provider_timeouts_total": 1.0,
                "provider_retries_total": 2.0,
            }
        },
        provider_requests_total=14.0,
        provider_timeouts_total=3.0,
        provider_retries_total=2.0,
    )

    assert deltas == {
        "provider_requests_delta_run": 4.0,
        "provider_timeouts_delta_run": 2.0,
        "provider_retries_delta_run": 0.0,
        "provider_timeout_rate_run": 0.5,
    }


def test_profile_report_helpers_validate_baseline_contract(tmp_path: Path):
    baseline = tmp_path / "baseline.json"
    baseline.write_text(
        json.dumps(
            {
                "manifest_name": "baseline_demo",
                "baseline_valid": True,
                "elapsed_seconds": 12.0,
                "top_phases": [],
                "stable_counters": {},
            }
        ),
        encoding="utf-8",
    )

    loaded = reports.load_expected_baseline(
        baseline,
        lambda path: json.loads(path.read_text(encoding="utf-8")),
    )

    assert loaded["manifest_name"] == "baseline_demo"
    assert reports.compare_timing_metric("elapsed_seconds", 10.0, 13.0, 20.0)["status"] == "fail"

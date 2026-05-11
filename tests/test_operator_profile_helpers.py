import json
from pathlib import Path
from types import SimpleNamespace

from scripts import operator_profile_artifacts as artifacts
from scripts import operator_profile_metrics as metrics
from scripts import operator_profile_reports as reports
from scripts import operator_profile_worker_metrics as worker_metrics
from scripts import profile_pipeline_commands as pipeline_commands
from scripts import profile_pipeline_results as pipeline_results


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


def test_profile_result_writer_preserves_result_manifest_keys(monkeypatch, tmp_path: Path):
    perf_values = iter([10.0, 75.4321])
    monkeypatch.setattr(pipeline_results.time, "perf_counter", lambda: next(perf_values))
    written = {}

    def _write_json(path: Path, payload: dict) -> None:
        written["path"] = path
        written["payload"] = payload

    pipeline_results.write_result_manifest(
        write_json=_write_json,
        segment_status_from_log=lambda _path: {"notes": [], "flags": {}},
        utc_now_iso=lambda: "2026-04-01T00:02:00+00:00",
        run_dir=tmp_path,
        run_id="profile_run",
        status="completed",
        started_at="2026-04-01T00:00:00+00:00",
        started=10.0,
        include_batch=False,
        command_segments=[
            {"name": "pipeline", "status": "completed", "elapsed_seconds": 12.3456},
        ],
        command_log=tmp_path / "commands.log",
        error_message=None,
    )

    payload = written["payload"]
    assert written["path"] == tmp_path / "result.json"
    assert sorted(payload) == [
        "elapsed_seconds",
        "error",
        "finished_at",
        "include_batch",
        "profile",
        "quality",
        "run_id",
        "segments",
        "started_at",
        "status",
        "totals",
    ]
    assert payload["totals"] == {
        "core_elapsed_seconds": 12.346,
        "batch_elapsed_seconds": None,
        "combined_elapsed_seconds": 12.346,
    }
    assert payload["profile"]["workload_only"] is True


def test_profile_run_manifest_writer_preserves_manifest_package_and_profile_env(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("LOCAL_AI_BACKEND", "http")
    monkeypatch.delenv("WORKER_POOL", raising=False)
    written = {}

    def _write_json(path: Path, payload: dict) -> None:
        written["path"] = path
        written["payload"] = payload

    run_manifest = pipeline_results.write_run_manifest(
        write_json=_write_json,
        utc_now_iso=lambda: "2026-04-01T00:00:00+00:00",
        run_dir=tmp_path,
        run_id="profile_run",
        mode="baseline",
        city="san_mateo",
        include_batch=True,
        catalog_ids=[101, 102],
        provider_counters_before_run={"requests": 3.0},
        manifest_package={
            "schema_version": 1,
            "manifest_name": "baseline-manifest",
            "strata": {"segment": [101], "summary": [102]},
            "expected_phase_coverage": {"segment": 1, "summary": 1},
        },
    )

    assert written["path"] == tmp_path / "run_manifest.json"
    assert written["payload"] == run_manifest
    assert run_manifest["baseline_valid"] is True
    assert run_manifest["catalog_count"] == 2
    assert run_manifest["include_batch"] is True
    assert run_manifest["profile"] == {"LOCAL_AI_BACKEND": "http"}
    assert run_manifest["manifest_package"] == {
        "schema_version": 1,
        "manifest_name": "baseline-manifest",
        "phase_selected_counts": {"segment": 1, "summary": 1},
        "expected_phase_coverage": {"segment": 1, "summary": 1},
    }


def test_profile_command_helpers_preserve_env_and_docker_command(monkeypatch):
    args = SimpleNamespace(mode="baseline", skip_batch=False)
    monkeypatch.setenv("UNRELATED_OPERATOR_SETTING", "kept")

    env = pipeline_commands.profile_env(
        run_id="profile_run",
        mode="baseline",
        artifact_dir="experiments/results/profile_run",
        baseline_valid=True,
        manifest_path="experiments/results/profile_run/catalog_manifest.txt",
    )
    commands = pipeline_commands.build_profile_commands(
        args=args,
        core_service="api",
        batch_service="worker",
        run_id="profile_run",
        artifact_dir_rel="experiments/results/profile_run",
        manifest_rel="experiments/results/profile_run/catalog_manifest.txt",
    )

    assert env["UNRELATED_OPERATOR_SETTING"] == "kept"
    assert env["TC_PROFILE_BASELINE_VALID"] == "1"
    assert env["TC_PROFILE_WORKLOAD_ONLY"] == "1"
    assert [command[-1] for command in commands] == ["run_pipeline.py", "run_batch_enrichment.py"]
    assert commands[0][:4] == ["docker", "compose", "exec", "-T"]
    assert "TC_PROFILE_BASELINE_VALID=1" in commands[0]
    assert commands[1][commands[1].index("-w") + 1] == "/app/pipeline"


def test_worker_metrics_prefers_endpoint_with_provider_series(monkeypatch):
    calls = []

    def _ok(cmd, **_kwargs):
        calls.append(cmd)
        return 'tc_provider_requests_total{provider="http"} 1\n'

    monkeypatch.setattr(worker_metrics.subprocess, "check_output", _ok)
    raw, err = worker_metrics.fetch_worker_metrics_via_docker()

    assert raw == 'tc_provider_requests_total{provider="http"} 1\n'
    assert err is None
    assert len(calls) == 1
    assert "localhost:8001/metrics" in calls[0][-1]


def test_worker_metrics_compat_wrapper_uses_existing_docker_exec_seam(monkeypatch):
    probes = []

    def _compat_probe(script: str) -> str:
        probes.append(script)
        return 'tc_provider_requests_total{provider="http"} 2\n'

    monkeypatch.setattr(metrics, "docker_exec_python", _compat_probe)
    raw, err = metrics.fetch_worker_metrics_via_docker()

    assert raw == 'tc_provider_requests_total{provider="http"} 2\n'
    assert err is None
    assert probes == [worker_metrics.WORKER_HTTP_METRICS_PROBE]


def test_worker_metrics_falls_back_to_collector_when_endpoint_lacks_provider_series(monkeypatch):
    responses = iter(
        [
            "python_gc_objects_collected_total 1\n",
            "python_gc_objects_collected_total 2\n",
            'tc_provider_requests_total{provider="http"} 3\n',
        ]
    )
    calls = []

    def _sequenced(cmd, **_kwargs):
        calls.append(cmd)
        return next(responses)

    monkeypatch.setattr(worker_metrics.subprocess, "check_output", _sequenced)
    monkeypatch.setattr(worker_metrics.time, "sleep", lambda *_args, **_kwargs: None)
    raw, err = worker_metrics.fetch_worker_metrics_via_docker()

    assert raw == 'tc_provider_requests_total{provider="http"} 3\n'
    assert err is None
    assert len(calls) == 3
    assert "localhost:8001/metrics" in calls[0][-1]
    assert "localhost:8001/metrics" in calls[1][-1]
    assert "RedisProviderMetricsCollector" in calls[2][-1]


def test_worker_metrics_reports_aggregated_strategy_errors(monkeypatch):
    def _empty(_cmd, **_kwargs):
        return ""

    monkeypatch.setattr(worker_metrics.subprocess, "check_output", _empty)
    monkeypatch.setattr(worker_metrics.time, "sleep", lambda *_args, **_kwargs: None)
    raw, err = worker_metrics.fetch_worker_metrics_via_docker()

    assert raw == ""
    assert err is not None
    assert "worker_http[attempt=1] empty_output" in err
    assert "worker_http[attempt=2] empty_output" in err
    assert "worker_registry[attempt=1] empty_output" in err
    assert "worker_registry[attempt=2] empty_output" in err


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

import importlib.util
import json
from pathlib import Path


spec = importlib.util.spec_from_file_location("collect_soak_metrics", Path("scripts/collect_soak_metrics.py"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_provider_metrics_state_no_provider_series():
    present, reason = mod._provider_metrics_state(
        [{"name": "tc_other_metric", "labels": {}, "value": 1.0}],
        None,
    )
    assert not present
    assert reason == "no_provider_series"


def test_day_summary_marks_provider_metrics_reason(monkeypatch, tmp_path):
    worker_metrics = "\n".join(
        [
            'tc_provider_requests_total{provider="http",operation="summarize_text",model="m",outcome="ok"} 2',
            'tc_provider_timeouts_total{provider="http",operation="summarize_text",model="m"} 0',
        ]
    )
    monkeypatch.setattr(mod, "_fetch_worker_metrics_via_docker", lambda: (worker_metrics, None))
    monkeypatch.setattr(mod, "_fetch_text", lambda *_args, **_kwargs: "up 1\n")

    run_id = "soak_reason_flags"
    run_dir = tmp_path / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "run_manifest.json").write_text(
        json.dumps(
            {
                "catalog_ids": [609, 933],
                "catalog_count": 2,
                "profile": {"LOCAL_AI_BACKEND": "http"},
                "provider_counters_before_run": {
                    "provider_requests_total": 1.0,
                    "provider_timeouts_total": 0.0,
                    "provider_retries_total": 0.0,
                },
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "tasks.jsonl").write_text(
        "\n".join(
            [
                json.dumps({"catalog_id": 609, "phase": "segment", "duration_s": 12.5}),
                json.dumps({"catalog_id": 933, "phase": "summarize", "duration_s": 6.25}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "collect_soak_metrics.py",
            "--run-id",
            run_id,
            "--output-dir",
            str(tmp_path),
            "--api-url",
            "http://localhost:8000",
        ],
    )
    assert mod.main() == 0
    day_summary = json.loads((tmp_path / run_id / "day_summary.json").read_text(encoding="utf-8"))
    assert day_summary["provider_metrics_present"] is True
    assert day_summary["provider_metrics_reason"] == "ok"
    assert day_summary["provider_requests_delta_run"] == 1.0
    assert day_summary["provider_timeouts_delta_run"] == 0.0
    assert day_summary["slowest_phase"] == "segment"
    assert day_summary["slowest_catalog_id"] == 609
    assert day_summary["run_manifest_present"] is True


def test_day_summary_includes_submission_failure_breakdown(monkeypatch, tmp_path):
    monkeypatch.setattr(mod, "_fetch_worker_metrics_via_docker", lambda: ("", "worker scrape failed"))
    monkeypatch.setattr(mod, "_fetch_text", lambda *_args, **_kwargs: "up 1\n")

    run_id = "soak_failure_breakdown"
    run_dir = tmp_path / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "run_manifest.json").write_text(
        json.dumps({"catalog_ids": [1], "catalog_count": 1, "profile": {"LOCAL_AI_BACKEND": "http"}}),
        encoding="utf-8",
    )
    (run_dir / "tasks.jsonl").write_text(
        "\n".join(
            [
                json.dumps({"catalog_id": 1, "phase": "segment", "status": "failed", "error": "task_submission_error"}),
                json.dumps(
                    {
                        "catalog_id": 1,
                        "phase": "summarize",
                        "status": "failed",
                        "error": "unexpected_non_processing_status:cached",
                    }
                ),
                json.dumps({"catalog_id": 1, "phase": "extract", "status": "failed", "error": "missing_task_id"}),
                json.dumps({"catalog_id": 1, "phase": "extract", "status": "failed", "error": "task_poll_timeout"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "collect_soak_metrics.py",
            "--run-id",
            run_id,
            "--output-dir",
            str(tmp_path),
            "--api-url",
            "http://localhost:8000",
        ],
    )
    assert mod.main() == 0
    day_summary = json.loads((tmp_path / run_id / "day_summary.json").read_text(encoding="utf-8"))
    assert day_summary["task_submission_failures"] == 3
    assert day_summary["task_submission_error_failures"] == 1
    assert day_summary["unexpected_non_processing_status_failures"] == 1
    assert day_summary["missing_task_id_failures"] == 1
    assert day_summary["task_poll_timeouts"] == 1


def test_day_summary_uses_zero_manifest_baseline_without_provider_series(monkeypatch, tmp_path):
    monkeypatch.setattr(mod, "_fetch_worker_metrics_via_docker", lambda: ("", None))
    monkeypatch.setattr(mod, "_fetch_text", lambda *_args, **_kwargs: "up 1\n")

    run_id = "soak_zero_baseline"
    run_dir = tmp_path / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "run_manifest.json").write_text(
        json.dumps(
            {
                "catalog_ids": [609],
                "catalog_count": 1,
                "profile": {"LOCAL_AI_BACKEND": "http"},
                "provider_counters_before_run": {
                    "provider_requests_total": 0.0,
                    "provider_timeouts_total": 0.0,
                    "provider_retries_total": 0.0,
                },
                "provider_counters_before_run_available": True,
                "provider_counters_before_run_source": "zero_baseline_no_provider_series",
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "tasks.jsonl").write_text("", encoding="utf-8")
    monkeypatch.setattr(
        "sys.argv",
        [
            "collect_soak_metrics.py",
            "--run-id",
            run_id,
            "--output-dir",
            str(tmp_path),
            "--api-url",
            "http://localhost:8000",
        ],
    )

    assert mod.main() == 0

    day_summary = json.loads((tmp_path / run_id / "day_summary.json").read_text(encoding="utf-8"))
    assert day_summary["provider_metrics_present"] is False
    assert day_summary["provider_metrics_reason"] == "no_provider_series"
    assert day_summary["provider_requests_delta_run"] == 0.0
    assert day_summary["provider_timeouts_delta_run"] == 0.0
    assert day_summary["provider_retries_delta_run"] == 0.0
    assert day_summary["provider_timeout_rate_run"] is None


def test_day_summary_marks_tc_prefixed_baseline_as_inconclusive(monkeypatch, tmp_path):
    worker_metrics = "\n".join(
        [
            'tc_provider_requests_total{provider="http",operation="extract_agenda",model="m",outcome="ok"} 117',
            'tc_provider_timeouts_total{provider="http",operation="extract_agenda",model="m"} 25',
            'tc_provider_retries_total{provider="http",operation="extract_agenda",model="m"} 16',
        ]
    )
    monkeypatch.setattr(mod, "_fetch_worker_metrics_via_docker", lambda: (worker_metrics, None))
    monkeypatch.setattr(mod, "_fetch_text", lambda *_args, **_kwargs: "up 1\n")

    run_id = "soak_tc_prefixed_baseline"
    run_dir = tmp_path / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "run_manifest.json").write_text(
        json.dumps(
            {
                "catalog_ids": [609],
                "catalog_count": 1,
                "profile": {"LOCAL_AI_BACKEND": "http"},
                "provider_counters_before_run": {
                    "tc_provider_requests_total": 113.0,
                    "tc_provider_timeouts_total": 25.0,
                    "tc_provider_retries_total": 16.0,
                },
                "provider_counters_before_run_available": True,
                "provider_counters_before_run_source": "worker_registry",
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "tasks.jsonl").write_text("", encoding="utf-8")
    monkeypatch.setattr(
        "sys.argv",
        [
            "collect_soak_metrics.py",
            "--run-id",
            run_id,
            "--output-dir",
            str(tmp_path),
            "--api-url",
            "http://localhost:8000",
        ],
    )

    assert mod.main() == 0

    day_summary = json.loads((tmp_path / run_id / "day_summary.json").read_text(encoding="utf-8"))
    assert day_summary["provider_requests_total"] == 117.0
    assert day_summary["provider_timeouts_total"] == 25.0
    assert day_summary["provider_retries_total"] == 16.0
    assert day_summary["provider_requests_delta_run"] is None
    assert day_summary["provider_timeouts_delta_run"] is None
    assert day_summary["provider_retries_delta_run"] is None
    assert day_summary["provider_timeout_rate_run"] is None

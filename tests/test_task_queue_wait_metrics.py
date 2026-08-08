import json

from prometheus_client import generate_latest

from pipeline import metrics
from pipeline import profiling


class _FakeTask:
    name = "pipeline.tasks.generate_summary_task"

    class request:
        headers = {}
        delivery_info = {"routing_key": "celery"}
        args = (123,)


def test_queue_wait_metric_and_task_context_are_recorded(monkeypatch, tmp_path):
    _FakeTask.request.headers = {
        "tc_queued_at": "1.0",
        "tc_profile_run_id": "run_1",
        "tc_profile_mode": "triage",
        "tc_profile_artifact_dir": str(tmp_path / "profile"),
        "tc_profile_baseline_valid": "0",
    }
    monkeypatch.setattr(metrics.time, "time", lambda: 3.5)
    monkeypatch.setattr(metrics.time, "perf_counter", lambda: 10.0)

    metrics._task_prerun(task_id="abc", task=_FakeTask())
    monkeypatch.setattr(metrics.time, "perf_counter", lambda: 12.0)
    metrics._task_postrun(task_id="abc", task=_FakeTask(), state="SUCCESS")

    payload = generate_latest().decode("utf-8", errors="ignore")
    assert "tc_task_queue_wait_seconds" in payload
    assert "tc_pipeline_phase_duration_seconds" in payload


def test_task_prerun_handles_missing_or_invalid_queue_timestamp(monkeypatch):
    _FakeTask.request.headers = {"tc_queued_at": "not-a-number"}
    monkeypatch.setattr(metrics.time, "perf_counter", lambda: 20.0)

    metrics._task_prerun(task_id="bad-queued-at", task=_FakeTask())

    context = metrics._TASK_CONTEXT["bad-queued-at"]
    assert context.queue_wait_s is None

    metrics._TASK_START.pop("bad-queued-at", None)
    metrics._TASK_CONTEXT.pop("bad-queued-at", None)


def test_diagnostic_validity_propagates_from_publish_header_to_task_span(monkeypatch, tmp_path):
    artifact_dir = tmp_path / "profile"
    monkeypatch.setenv(profiling.PROFILE_RUN_ID_ENV, "diagnostic_run")
    monkeypatch.setenv(profiling.PROFILE_MODE_ENV, "baseline")
    monkeypatch.setenv(profiling.PROFILE_ARTIFACT_DIR_ENV, str(artifact_dir))
    monkeypatch.setenv(profiling.PROFILE_BASELINE_VALID_ENV, "0")
    monkeypatch.setattr(metrics.time, "time", lambda: 1.0)
    monkeypatch.setattr(metrics.time, "perf_counter", lambda: 2.0)

    headers: dict[str, object] = {}
    metrics._before_task_publish(headers=headers)
    _FakeTask.request.headers = headers
    metrics._task_prerun(task_id="diagnostic-task", task=_FakeTask())
    monkeypatch.setattr(metrics.time, "perf_counter", lambda: 3.0)
    metrics._task_postrun(task_id="diagnostic-task", task=_FakeTask(), state="SUCCESS")

    task_spans = [
        json.loads(line)
        for line in (artifact_dir / "spans.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert headers["tc_profile_baseline_valid"] == "0"
    assert task_spans[-1]["event_type"] == "task_span"
    assert task_spans[-1]["baseline_valid"] is False

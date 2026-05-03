from prometheus_client import generate_latest

from pipeline import metrics


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

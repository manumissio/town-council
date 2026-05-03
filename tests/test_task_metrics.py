from prometheus_client import generate_latest

from pipeline import metrics


class _FakeMetric:
    def __init__(self):
        self.labels_seen = []
        self.observed = []

    def labels(self, **labels):
        self.labels_seen.append(labels)
        return self

    def observe(self, value):
        self.observed.append(value)


def test_worker_task_metrics_helpers_exist_and_export():
    # Import registers metric collectors. We do not start an HTTP server in tests.
    from pipeline.metrics import (
        record_task_duration,
        record_task_failure,
        record_task_retry,
    )

    record_task_duration("pipeline.tasks.segment_agenda_task", "success", 0.123)
    record_task_failure("pipeline.tasks.segment_agenda_task", "RuntimeError")
    record_task_retry("pipeline.tasks.segment_agenda_task")

    payload = generate_latest().decode("utf-8", errors="ignore")
    assert "tc_celery_task_duration_seconds" in payload
    assert "tc_celery_task_failures_total" in payload
    assert "tc_celery_task_retries_total" in payload


def test_task_recorder_uses_metrics_facade_patch(monkeypatch):
    fake_queue_wait = _FakeMetric()
    monkeypatch.setattr(metrics, "TASK_QUEUE_WAIT_SECONDS", fake_queue_wait)

    metrics.record_task_queue_wait("pipeline.tasks.generate_summary_task", "celery", 1.25)

    assert fake_queue_wait.labels_seen == [{"task_name": "pipeline.tasks.generate_summary_task", "queue": "celery"}]
    assert fake_queue_wait.observed == [1.25]


def test_task_failure_clears_timing_context(monkeypatch):
    task_id = "failure-task"
    metrics._TASK_START[task_id] = 5.0
    metrics._TASK_CONTEXT[task_id] = metrics.TaskProfileContext(
        task_name="pipeline.tasks.generate_summary_task",
        queue="celery",
        queue_wait_s=None,
        queued_at=None,
        run_id=None,
        mode=None,
        artifact_dir=None,
        baseline_valid=None,
        catalog_id=123,
    )
    monkeypatch.setattr(metrics.time, "perf_counter", lambda: 7.0)

    metrics._task_failure(
        task_id=task_id,
        exception=RuntimeError("boom"),
        sender=type("_Task", (), {"name": "pipeline.tasks.generate_summary_task"})(),
    )

    assert task_id not in metrics._TASK_START
    assert task_id not in metrics._TASK_CONTEXT

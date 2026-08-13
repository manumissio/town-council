from prometheus_client import generate_latest

from pipeline import metrics


def _metric_sample_value(metric, sample_name: str, expected_labels: dict[str, str]) -> float:
    for collected_metric in metric.collect():
        for sample in collected_metric.samples:
            if sample.name == sample_name and all(
                sample.labels.get(label_name) == label_value
                for label_name, label_value in expected_labels.items()
            ):
                return float(sample.value)
    return 0.0


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


def test_task_recorder_exports_queue_wait_sample():
    labels = {
        "task_name": "pipeline.tasks.generate_summary_task",
        "queue": "celery",
    }
    count_before = _metric_sample_value(
        metrics.TASK_QUEUE_WAIT_SECONDS,
        "tc_task_queue_wait_seconds_count",
        labels,
    )

    metrics.record_task_queue_wait("pipeline.tasks.generate_summary_task", "celery", 1.25)

    assert (
        _metric_sample_value(
            metrics.TASK_QUEUE_WAIT_SECONDS,
            "tc_task_queue_wait_seconds_count",
            labels,
        )
        == count_before + 1
    )


def test_task_failure_clears_timing_context(monkeypatch):
    task_id = "failure-task"
    metrics._TASK_START[task_id] = 5.0
    metrics._TASK_CONTEXT[task_id] = metrics.TaskProfileContext(
        task_name="pipeline.tasks.generate_summary_task",
        task_id=task_id,
        execution_id="00000000-0000-0000-0000-000000000001",
        retry_ordinal=0,
        redelivered=None,
        queue="celery",
        queue_wait_s=None,
        queued_at=None,
        run_id=None,
        mode=None,
        artifact_dir=None,
        catalog_id=123,
        observer_at_start=0.0,
    )
    monkeypatch.setattr(metrics.time, "perf_counter", lambda: 7.0)

    metrics._task_failure(
        task_id=task_id,
        exception=RuntimeError("boom"),
        sender=type("_Task", (), {"name": "pipeline.tasks.generate_summary_task"})(),
    )

    assert task_id not in metrics._TASK_START
    assert task_id not in metrics._TASK_CONTEXT

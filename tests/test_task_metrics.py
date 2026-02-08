from prometheus_client import generate_latest


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


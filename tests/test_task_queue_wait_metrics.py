import json
from uuid import UUID

from celery import Celery
from kombu.exceptions import SerializerNotInstalled
from prometheus_client import generate_latest
import pytest

from pipeline import metrics
from pipeline import profiling


class _FakeTask:
    name = "pipeline.tasks.generate_summary_task"

    class request:
        headers = {}
        delivery_info = {"routing_key": "celery"}
        args = (123,)
        retries = 0


def _task_spans(artifact_dir):
    profile_events = [
        json.loads(line) for line in (artifact_dir / "spans.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    return [profile_event for profile_event in profile_events if profile_event["event_type"] == "task_span"]


def _task_dispatches(artifact_dir):
    profile_events = [
        json.loads(line) for line in (artifact_dir / "spans.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    return [profile_event for profile_event in profile_events if profile_event["event_type"] == "task_dispatch"]


def _memory_broker_app(app_name: str, *, task_protocol: int = 2) -> Celery:
    celery_app = Celery(app_name, broker="memory://")
    celery_app.conf.task_protocol = task_protocol
    return celery_app


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
    monkeypatch.setattr(metrics.time, "time", lambda: 2.0)
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


def test_task_spans_distinguish_retry_and_redelivery_attempts(monkeypatch, tmp_path):
    artifact_dir = tmp_path / "profile"
    monkeypatch.setenv(profiling.PROFILE_RUN_ID_ENV, "task_attempt_run")
    monkeypatch.setenv(profiling.PROFILE_MODE_ENV, "baseline")
    monkeypatch.setenv(profiling.PROFILE_ARTIFACT_DIR_ENV, str(artifact_dir))
    monkeypatch.setenv(profiling.PROFILE_BASELINE_VALID_ENV, "0")
    monkeypatch.setattr(metrics.time, "time", lambda: 1.0)

    headers: dict[str, object] = {}
    metrics._before_task_publish(headers=headers)
    monkeypatch.setattr(metrics.time, "time", lambda: 2.0)
    _FakeTask.request.headers = headers

    attempt_contexts = [(0, False), (0, True), (1, False), (1, True)]
    for attempt_index, (retry_ordinal, redelivered) in enumerate(attempt_contexts):
        _FakeTask.request.retries = retry_ordinal
        _FakeTask.request.delivery_info = {"routing_key": "celery", "redelivered": redelivered}
        attempt_started = float(attempt_index * 2 + 2)
        monkeypatch.setattr(metrics.time, "perf_counter", lambda value=attempt_started: value)
        metrics._task_prerun(task_id="shared-task-id", task=_FakeTask())
        monkeypatch.setattr(metrics.time, "perf_counter", lambda value=attempt_started + 1.0: value)
        metrics._task_postrun(task_id="shared-task-id", task=_FakeTask(), state="SUCCESS")

    task_spans = _task_spans(artifact_dir)
    assert [task_span["task_id"] for task_span in task_spans] == ["shared-task-id"] * len(attempt_contexts)
    assert [
        (task_span["retry_ordinal"], task_span["redelivered"]) for task_span in task_spans
    ] == attempt_contexts
    execution_ids = [task_span["execution_id"] for task_span in task_spans]
    assert all(str(UUID(execution_id)) == execution_id for execution_id in execution_ids)
    assert len(set(execution_ids)) == len(attempt_contexts)
    assert [task_span["queue_wait_s"] for task_span in task_spans] == [1.0, None, None, None]


def test_task_span_preserves_unknown_optional_delivery_metadata(monkeypatch, tmp_path):
    artifact_dir = tmp_path / "profile"
    _FakeTask.request.headers = {
        "tc_profile_run_id": "invalid_metadata_run",
        "tc_profile_mode": "triage",
        "tc_profile_artifact_dir": str(artifact_dir),
        "tc_profile_baseline_valid": "0",
    }
    _FakeTask.request.retries = -1
    _FakeTask.request.delivery_info = {"routing_key": "celery"}
    monkeypatch.setattr(metrics.time, "perf_counter", lambda: 10.0)

    metrics._task_prerun(task_id="invalid-metadata-task", task=_FakeTask())
    monkeypatch.setattr(metrics.time, "perf_counter", lambda: 11.0)
    metrics._task_postrun(task_id="invalid-metadata-task", task=_FakeTask(), state="SUCCESS")

    task_span = _task_spans(artifact_dir)[0]
    assert task_span["retry_ordinal"] is None
    assert task_span["redelivered"] is None
    assert task_span["queue_wait_s"] is None


def test_task_span_omits_queue_wait_when_redelivery_metadata_is_unknown(monkeypatch, tmp_path):
    artifact_dir = tmp_path / "profile"
    _FakeTask.request.headers = {
        "tc_profile_run_id": "unknown_redelivery_run",
        "tc_profile_mode": "triage",
        "tc_profile_artifact_dir": str(artifact_dir),
        "tc_profile_baseline_valid": "0",
        "tc_queued_at": "1.0",
    }
    _FakeTask.request.retries = 0
    _FakeTask.request.delivery_info = {"routing_key": "celery"}
    monkeypatch.setattr(metrics.time, "time", lambda: 2.0)
    monkeypatch.setattr(metrics.time, "perf_counter", lambda: 10.0)

    metrics._task_prerun(task_id="unknown-redelivery-task", task=_FakeTask())
    monkeypatch.setattr(metrics.time, "perf_counter", lambda: 11.0)
    metrics._task_postrun(task_id="unknown-redelivery-task", task=_FakeTask(), state="SUCCESS")

    task_span = _task_spans(artifact_dir)[0]
    assert task_span["retry_ordinal"] == 0
    assert task_span["redelivered"] is None
    assert task_span["queue_wait_s"] is None


def test_task_attempt_emits_start_before_matching_finish(monkeypatch, tmp_path):
    artifact_dir = tmp_path / "profile"
    _FakeTask.request.headers = {
        "tc_profile_run_id": "task_lifecycle_run",
        "tc_profile_mode": "baseline",
        "tc_profile_artifact_dir": str(artifact_dir),
        "tc_profile_baseline_valid": "0",
        "tc_queued_at": "1.0",
    }
    _FakeTask.request.retries = 0
    _FakeTask.request.delivery_info = {"routing_key": "celery", "redelivered": False}
    monkeypatch.setattr(metrics.time, "time", lambda: 2.0)
    monkeypatch.setattr(metrics.time, "perf_counter", lambda: 10.0)

    metrics._task_prerun(task_id="lifecycle-task", task=_FakeTask())
    monkeypatch.setattr(metrics.time, "perf_counter", lambda: 11.0)
    metrics._task_postrun(task_id="lifecycle-task", task=_FakeTask(), state="SUCCESS")

    profile_events = [
        json.loads(line)
        for line in (artifact_dir / "spans.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [profile_event["event_type"] for profile_event in profile_events] == [
        "task_start",
        "task_span",
    ]
    assert profile_events[0]["execution_id"] == profile_events[1]["execution_id"]
    assert profile_events[0]["task_id"] == profile_events[1]["task_id"] == "lifecycle-task"


def test_failed_task_span_keeps_attempt_identity_without_postrun_duplicate(monkeypatch, tmp_path):
    artifact_dir = tmp_path / "profile"
    _FakeTask.request.headers = {
        "tc_profile_run_id": "failed_task_run",
        "tc_profile_mode": "triage",
        "tc_profile_artifact_dir": str(artifact_dir),
        "tc_profile_baseline_valid": "0",
    }
    _FakeTask.request.retries = 2
    _FakeTask.request.delivery_info = {"routing_key": "celery", "redelivered": False}
    monkeypatch.setattr(metrics.time, "perf_counter", lambda: 20.0)

    metrics._task_prerun(task_id="failed-task-id", task=_FakeTask())
    monkeypatch.setattr(metrics.time, "perf_counter", lambda: 21.0)
    metrics._task_failure(
        task_id="failed-task-id",
        exception=RuntimeError("boom"),
        sender=_FakeTask(),
    )
    metrics._task_postrun(task_id="failed-task-id", task=_FakeTask(), state="FAILURE")

    task_spans = _task_spans(artifact_dir)
    assert len(task_spans) == 1
    assert task_spans[0]["task_id"] == "failed-task-id"
    assert str(UUID(task_spans[0]["execution_id"])) == task_spans[0]["execution_id"]
    assert task_spans[0]["retry_ordinal"] == 2
    assert task_spans[0]["redelivered"] is False
    assert task_spans[0]["outcome"] == "failure"
    assert task_spans[0]["metadata"] == {"exception_type": "RuntimeError"}


def test_task_publish_records_paired_dispatch_boundaries(monkeypatch, tmp_path):
    artifact_dir = tmp_path / "profile"
    monkeypatch.setenv(profiling.PROFILE_RUN_ID_ENV, "dispatch_run")
    monkeypatch.setenv(profiling.PROFILE_MODE_ENV, "baseline")
    monkeypatch.setenv(profiling.PROFILE_ARTIFACT_DIR_ENV, str(artifact_dir))
    monkeypatch.setenv(profiling.PROFILE_BASELINE_VALID_ENV, "0")
    celery_app = _memory_broker_app("profile-dispatch-success")

    dispatch_result = celery_app.send_task(
        "pipeline.tasks.generate_summary_task",
        args=(456,),
        queue="enrichment",
    )

    dispatches = _task_dispatches(artifact_dir)
    assert [dispatch["boundary"] for dispatch in dispatches] == ["before", "after"]
    for dispatch in dispatches:
        assert dispatch["task_id"] == dispatch_result.id
        assert dispatch["task_name"] == "pipeline.tasks.generate_summary_task"
        assert dispatch["queue"] == "enrichment"
        assert dispatch["retry_ordinal"] == 0
        assert dispatch["catalog_id"] == 456
        assert dispatch["baseline_valid"] is False
        assert "duration_s" not in dispatch
        assert "outcome" not in dispatch


def test_task_publish_before_event_remains_unpaired_when_publish_does_not_complete(monkeypatch, tmp_path):
    artifact_dir = tmp_path / "profile"
    monkeypatch.setenv(profiling.PROFILE_RUN_ID_ENV, "failed_dispatch_run")
    monkeypatch.setenv(profiling.PROFILE_ARTIFACT_DIR_ENV, str(artifact_dir))
    celery_app = _memory_broker_app("profile-dispatch-failure")

    with pytest.raises(SerializerNotInstalled):
        celery_app.send_task(
            "pipeline.tasks.generate_summary_task",
            args=(789,),
            serializer="missing-serializer",
        )

    dispatches = _task_dispatches(artifact_dir)
    assert [dispatch["boundary"] for dispatch in dispatches] == ["before"]


def test_task_publish_omits_dispatch_without_profile_or_task_id(monkeypatch, tmp_path):
    artifact_dir = tmp_path / "profile"
    headers: dict[str, object] = {"id": "unprofiled-task-id"}

    metrics._before_task_publish(
        sender="pipeline.tasks.generate_summary_task",
        body=((1,), {}, {}),
        headers=headers,
        routing_key="celery",
    )
    assert not (artifact_dir / "spans.jsonl").exists()

    monkeypatch.setenv(profiling.PROFILE_RUN_ID_ENV, "missing_id_run")
    monkeypatch.setenv(profiling.PROFILE_ARTIFACT_DIR_ENV, str(artifact_dir))
    metrics._before_task_publish(
        sender="pipeline.tasks.generate_summary_task",
        body={"args": (1,)},
        headers={},
        routing_key="celery",
    )
    assert not (artifact_dir / "spans.jsonl").exists()


def test_task_publish_records_protocol_v1_dispatch_metadata(monkeypatch, tmp_path):
    artifact_dir = tmp_path / "profile"
    monkeypatch.setenv(profiling.PROFILE_RUN_ID_ENV, "dispatch_v1_run")
    monkeypatch.setenv(profiling.PROFILE_ARTIFACT_DIR_ENV, str(artifact_dir))
    celery_app = _memory_broker_app("profile-dispatch-v1", task_protocol=1)

    dispatch_result = celery_app.send_task(
        "pipeline.tasks.generate_summary_task",
        args=(654,),
        queue="enrichment",
    )

    dispatches = _task_dispatches(artifact_dir)
    assert [dispatch["boundary"] for dispatch in dispatches] == ["before", "after"]
    assert {dispatch["task_id"] for dispatch in dispatches} == {dispatch_result.id}
    assert {dispatch["retry_ordinal"] for dispatch in dispatches} == {0}
    assert {dispatch["catalog_id"] for dispatch in dispatches} == {654}


def test_task_retry_records_dispatch_from_inherited_profile_headers(monkeypatch, tmp_path):
    artifact_dir = tmp_path / "profile"
    for profile_env in (
        profiling.PROFILE_RUN_ID_ENV,
        profiling.PROFILE_MODE_ENV,
        profiling.PROFILE_ARTIFACT_DIR_ENV,
        profiling.PROFILE_BASELINE_VALID_ENV,
    ):
        monkeypatch.delenv(profile_env, raising=False)
    celery_app = _memory_broker_app("profile-dispatch-retry")

    @celery_app.task(bind=True, name="pipeline.tasks.profile_retry_probe")
    def profile_retry_probe(task: object, catalog_id: int) -> int:
        return catalog_id

    inherited_headers = {
        "tc_profile_run_id": "retry-dispatch-run",
        "tc_profile_mode": "baseline",
        "tc_profile_artifact_dir": str(artifact_dir),
        "tc_profile_baseline_valid": "0",
        "tc_queued_at": 1.0,
    }
    profile_retry_probe.push_request(
        id="retry-dispatch-id",
        args=(321,),
        kwargs={},
        retries=1,
        called_directly=False,
        is_eager=False,
        headers=inherited_headers,
        delivery_info={"exchange": "", "routing_key": "celery"},
    )
    try:
        profile_retry_probe.retry(args=(321,), kwargs={}, countdown=0, throw=False)
    finally:
        profile_retry_probe.pop_request()

    dispatches = _task_dispatches(artifact_dir)
    assert [dispatch["boundary"] for dispatch in dispatches] == ["before", "after"]
    assert {dispatch["task_id"] for dispatch in dispatches} == {"retry-dispatch-id"}
    assert {dispatch["retry_ordinal"] for dispatch in dispatches} == {2}
    assert {dispatch["catalog_id"] for dispatch in dispatches} == {321}
    assert all(dispatch["baseline_valid"] is False for dispatch in dispatches)


def test_task_publish_uses_safe_defaults_for_optional_dispatch_metadata(monkeypatch, tmp_path):
    artifact_dir = tmp_path / "profile"
    monkeypatch.setenv(profiling.PROFILE_RUN_ID_ENV, "dispatch_defaults_run")
    monkeypatch.setenv(profiling.PROFILE_ARTIFACT_DIR_ENV, str(artifact_dir))
    headers: dict[str, object] = {
        "id": "dispatch-defaults-id",
        "task": "pipeline.tasks.generate_summary_task",
        "retries": "invalid",
    }

    metrics._before_task_publish(
        sender=None,
        body=(("not-a-catalog-id",), {}, {}),
        headers=headers,
        routing_key=None,
    )

    dispatch = _task_dispatches(artifact_dir)[0]
    assert dispatch["task_name"] == "pipeline.tasks.generate_summary_task"
    assert dispatch["queue"] == "celery"
    assert dispatch["retry_ordinal"] == 0
    assert dispatch["catalog_id"] is None


def test_task_dispatch_and_task_span_remain_distinct_profile_events(monkeypatch, tmp_path):
    artifact_dir = tmp_path / "profile"
    monkeypatch.setenv(profiling.PROFILE_RUN_ID_ENV, "dispatch_execution_run")
    monkeypatch.setenv(profiling.PROFILE_ARTIFACT_DIR_ENV, str(artifact_dir))
    monkeypatch.setattr(metrics.time, "time", lambda: 1.0)
    monkeypatch.setattr(metrics.time, "perf_counter", lambda: 2.0)
    headers: dict[str, object] = {
        "id": "dispatch-execution-id",
        "task": "pipeline.tasks.generate_summary_task",
    }
    body = ((123,), {}, {})

    metrics._before_task_publish(
        sender="pipeline.tasks.generate_summary_task",
        body=body,
        headers=headers,
        routing_key="celery",
    )
    metrics._after_task_publish(
        sender="pipeline.tasks.generate_summary_task",
        body=body,
        headers=headers,
        routing_key="celery",
    )
    _FakeTask.request.headers = headers
    metrics._task_prerun(task_id="dispatch-execution-id", task=_FakeTask())
    monkeypatch.setattr(metrics.time, "perf_counter", lambda: 3.0)
    metrics._task_postrun(task_id="dispatch-execution-id", task=_FakeTask(), state="SUCCESS")

    profile_events = [
        json.loads(line) for line in (artifact_dir / "spans.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [profile_event["event_type"] for profile_event in profile_events] == [
        "task_dispatch",
        "task_dispatch",
        "task_span",
    ]

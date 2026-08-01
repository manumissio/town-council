import logging

import pytest

from pipeline import config, task_startup, tasks


def _disable_startup_purge(monkeypatch) -> None:
    monkeypatch.setenv("STARTUP_PURGE_DERIVED", "false")


def test_worker_ready_exits_on_unsafe_concurrency(monkeypatch):
    _disable_startup_purge(monkeypatch)
    monkeypatch.setattr(config, "LOCAL_AI_BACKEND", "inprocess")
    monkeypatch.setattr(config, "LOCAL_AI_ALLOW_MULTIPROCESS", False)
    monkeypatch.setattr(config, "LOCAL_AI_REQUIRE_SOLO_POOL", True)

    class _Sender:
        concurrency = 4
        argv = ["celery", "-A", "pipeline.tasks", "worker", "--pool=prefork", "--concurrency=4"]

    with pytest.raises(SystemExit):
        task_startup.run_startup_purge_on_worker_ready(sender=_Sender())


def test_worker_ready_exits_when_solo_pool_required_but_pool_not_provided(monkeypatch):
    _disable_startup_purge(monkeypatch)
    monkeypatch.setattr(config, "LOCAL_AI_BACKEND", "inprocess")
    monkeypatch.setattr(config, "LOCAL_AI_ALLOW_MULTIPROCESS", False)
    monkeypatch.setattr(config, "LOCAL_AI_REQUIRE_SOLO_POOL", True)

    class _Sender:
        concurrency = 1
        argv = ["celery", "-A", "pipeline.tasks", "worker", "--loglevel=info"]

    with pytest.raises(SystemExit):
        task_startup.run_startup_purge_on_worker_ready(sender=_Sender())


def test_worker_ready_exits_when_concurrency_gt_one_even_with_solo_pool(monkeypatch):
    _disable_startup_purge(monkeypatch)
    monkeypatch.setattr(config, "LOCAL_AI_BACKEND", "inprocess")
    monkeypatch.setattr(config, "LOCAL_AI_ALLOW_MULTIPROCESS", False)
    monkeypatch.setattr(config, "LOCAL_AI_REQUIRE_SOLO_POOL", True)

    class _Sender:
        concurrency = 2
        argv = ["celery", "-A", "pipeline.tasks", "worker", "--pool=solo", "--concurrency=2"]

    with pytest.raises(SystemExit):
        task_startup.run_startup_purge_on_worker_ready(sender=_Sender())


def test_worker_ready_allows_http_backend_without_inprocess_guardrails(monkeypatch, caplog):
    _disable_startup_purge(monkeypatch)
    monkeypatch.setattr(config, "LOCAL_AI_BACKEND", "http")

    class _Sender:
        concurrency = 4
        argv = ["celery", "-A", "pipeline.tasks", "worker", "--pool=prefork", "--concurrency=4"]

    with caplog.at_level(logging.INFO):
        task_startup.run_startup_purge_on_worker_ready(sender=_Sender())

    assert any("startup_purge_result=" in record.message for record in caplog.records)


def test_worker_ready_guardrail_check_failures_still_run_startup_purge(monkeypatch, caplog):
    _disable_startup_purge(monkeypatch)

    class _Sender:
        argv = ["celery", "-A", "pipeline.tasks", "worker", "--pool=solo", "--concurrency=1"]

        @property
        def concurrency(self):
            raise RuntimeError("guardrail blew up")

    with caplog.at_level(logging.INFO):
        task_startup.run_startup_purge_on_worker_ready(sender=_Sender())

    assert any("worker_ready.guardrail_check_failed" in record.message for record in caplog.records)
    assert any("startup_purge_result=" in record.message for record in caplog.records)


def test_worker_ready_treats_malformed_concurrency_as_unknown(monkeypatch, caplog):
    _disable_startup_purge(monkeypatch)
    monkeypatch.setattr(config, "LOCAL_AI_BACKEND", "inprocess")
    monkeypatch.setattr(config, "LOCAL_AI_ALLOW_MULTIPROCESS", False)
    monkeypatch.setattr(config, "LOCAL_AI_REQUIRE_SOLO_POOL", True)

    class _Sender:
        concurrency = "not-a-number"
        argv = ["celery", "-A", "pipeline.tasks", "worker", "--pool=solo"]

    with caplog.at_level(logging.INFO):
        task_startup.run_startup_purge_on_worker_ready(sender=_Sender())

    assert any("startup_purge_result=" in record.message for record in caplog.records)


def test_worker_ready_accepts_additional_celery_signal_keywords(monkeypatch):
    _disable_startup_purge(monkeypatch)
    monkeypatch.setattr(config, "LOCAL_AI_BACKEND", "http")

    tasks._run_startup_purge_on_worker_ready(sender=None, signal_name="worker_ready")

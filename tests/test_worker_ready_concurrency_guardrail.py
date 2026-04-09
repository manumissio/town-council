import pytest


def test_worker_ready_exits_on_unsafe_concurrency(monkeypatch):
    """
    If the Celery worker is configured in a way that implies multiprocess model duplication,
    the worker should fail fast (SystemExit) rather than OOMing later.
    """
    import pipeline.tasks as tasks

    monkeypatch.setattr(tasks, "LOCAL_AI_BACKEND", "inprocess")
    monkeypatch.setattr(tasks, "LOCAL_AI_ALLOW_MULTIPROCESS", False)
    monkeypatch.setattr(tasks, "LOCAL_AI_REQUIRE_SOLO_POOL", True)
    monkeypatch.setattr(tasks, "run_startup_purge_if_enabled", lambda: {"status": "skipped"})

    class _Sender:
        concurrency = 4
        argv = ["celery", "-A", "pipeline.tasks", "worker", "--loglevel=info", "--pool=prefork", "--concurrency=4"]

    with pytest.raises(SystemExit):
        tasks._run_startup_purge_on_worker_ready(sender=_Sender())


def test_worker_ready_exits_when_solo_pool_required_but_pool_not_provided(monkeypatch):
    import pipeline.tasks as tasks

    monkeypatch.setattr(tasks, "LOCAL_AI_BACKEND", "inprocess")
    monkeypatch.setattr(tasks, "LOCAL_AI_ALLOW_MULTIPROCESS", False)
    monkeypatch.setattr(tasks, "LOCAL_AI_REQUIRE_SOLO_POOL", True)
    monkeypatch.setattr(tasks, "run_startup_purge_if_enabled", lambda: {"status": "skipped"})

    class _Sender:
        concurrency = 1
        argv = ["celery", "-A", "pipeline.tasks", "worker", "--loglevel=info"]

    with pytest.raises(SystemExit):
        tasks._run_startup_purge_on_worker_ready(sender=_Sender())


def test_worker_ready_exits_when_concurrency_gt_one_even_with_solo_pool(monkeypatch):
    import pipeline.tasks as tasks

    monkeypatch.setattr(tasks, "LOCAL_AI_BACKEND", "inprocess")
    monkeypatch.setattr(tasks, "LOCAL_AI_ALLOW_MULTIPROCESS", False)
    monkeypatch.setattr(tasks, "LOCAL_AI_REQUIRE_SOLO_POOL", True)
    monkeypatch.setattr(tasks, "run_startup_purge_if_enabled", lambda: {"status": "skipped"})

    class _Sender:
        concurrency = 2
        argv = ["celery", "-A", "pipeline.tasks", "worker", "--pool=solo", "--concurrency=2"]

    with pytest.raises(SystemExit):
        tasks._run_startup_purge_on_worker_ready(sender=_Sender())


def test_worker_ready_allows_http_backend_without_inprocess_guardrails(monkeypatch):
    import pipeline.tasks as tasks

    purge_called = {"n": 0}
    monkeypatch.setattr(tasks, "LOCAL_AI_BACKEND", "http")
    monkeypatch.setattr(tasks, "LOCAL_AI_ALLOW_MULTIPROCESS", False)
    monkeypatch.setattr(tasks, "LOCAL_AI_REQUIRE_SOLO_POOL", True)
    monkeypatch.setattr(
        tasks,
        "run_startup_purge_if_enabled",
        lambda: purge_called.__setitem__("n", purge_called["n"] + 1) or {"status": "skipped"},
    )

    class _Sender:
        concurrency = 4
        argv = ["celery", "-A", "pipeline.tasks", "worker", "--pool=prefork", "--concurrency=4"]

    tasks._run_startup_purge_on_worker_ready(sender=_Sender())
    assert purge_called["n"] == 1


def test_worker_ready_guardrail_check_failures_still_run_startup_purge(monkeypatch):
    import pipeline.tasks as tasks

    purge_called = {"n": 0}
    monkeypatch.setattr(
        tasks,
        "local_ai_runtime_guardrail_message",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("guardrail blew up")),
    )
    monkeypatch.setattr(
        tasks,
        "run_startup_purge_if_enabled",
        lambda: purge_called.__setitem__("n", purge_called["n"] + 1) or {"status": "skipped"},
    )

    class _Sender:
        concurrency = 1
        argv = ["celery", "-A", "pipeline.tasks", "worker", "--pool=solo", "--concurrency=1"]

    tasks._run_startup_purge_on_worker_ready(sender=_Sender())

    assert purge_called["n"] == 1

import pytest


def test_worker_ready_exits_on_unsafe_concurrency(monkeypatch):
    """
    If the Celery worker is configured in a way that implies multiprocess model duplication,
    the worker should fail fast (SystemExit) rather than OOMing later.
    """
    import pipeline.tasks as tasks

    monkeypatch.setattr(tasks, "LOCAL_AI_ALLOW_MULTIPROCESS", False)
    monkeypatch.setattr(tasks, "LOCAL_AI_REQUIRE_SOLO_POOL", True)
    monkeypatch.setattr(tasks, "run_startup_purge_if_enabled", lambda: {"status": "skipped"})

    class _Sender:
        concurrency = 4
        argv = ["celery", "-A", "pipeline.tasks", "worker", "--loglevel=info", "--pool=prefork", "--concurrency=4"]

    with pytest.raises(SystemExit):
        tasks._run_startup_purge_on_worker_ready(sender=_Sender())


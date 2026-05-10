import sys
from unittest.mock import MagicMock

sys.modules["llama_cpp"] = MagicMock()


def test_api_task_routes_reexports_dispatch_facade():
    from api import task_dispatch, task_routes

    assert task_routes.INVALID_TASK_ID_DETAIL == task_dispatch.INVALID_TASK_ID_DETAIL
    assert task_routes.GENERATE_SUMMARY_TASK_NAME == task_dispatch.GENERATE_SUMMARY_TASK_NAME
    assert task_routes.GENERATE_TOPICS_TASK_NAME == task_dispatch.GENERATE_TOPICS_TASK_NAME
    assert task_routes.SEGMENT_AGENDA_TASK_NAME == task_dispatch.SEGMENT_AGENDA_TASK_NAME
    assert task_routes.EXTRACT_VOTES_TASK_NAME == task_dispatch.EXTRACT_VOTES_TASK_NAME
    assert task_routes.EXTRACT_TEXT_TASK_NAME == task_dispatch.EXTRACT_TEXT_TASK_NAME
    assert task_routes.TASK_DISPATCH_ERRORS == task_dispatch.TASK_DISPATCH_ERRORS
    assert task_routes._CeleryTaskProxy is task_dispatch._CeleryTaskProxy
    assert task_routes._enqueue_task is task_dispatch._enqueue_task
    assert task_routes.generate_summary_task is task_dispatch.generate_summary_task
    assert task_routes.extract_text_task is task_dispatch.extract_text_task


def test_pipeline_tasks_summary_services_use_pipeline_tasks_patch_seams(monkeypatch):
    import pipeline.tasks as tasks

    fake_local_ai = MagicMock(name="fake_local_ai")
    fake_reindex = MagicMock(name="fake_reindex")
    fake_embed_task = MagicMock()

    monkeypatch.setattr(tasks, "LocalAI", fake_local_ai)
    monkeypatch.setattr(tasks, "reindex_catalog", fake_reindex)
    monkeypatch.setattr(tasks, "embed_catalog_task", fake_embed_task)

    services = tasks._summary_generation_task_services()

    assert services.local_ai_factory is fake_local_ai
    assert services.reindex_catalog is fake_reindex
    assert services.embed_catalog is fake_embed_task.delay

import sys
from pathlib import Path
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


def test_api_task_route_helpers_do_not_import_main():
    helper_modules = (
        "api.task_route_summary",
        "api.task_route_segmentation",
        "api.task_route_generation",
        "api.task_route_support",
    )

    for module_name in helper_modules:
        module = __import__(module_name, fromlist=["__name__"])
        module_path = Path(module.__file__)
        assert "api.main" not in module_path.read_text(encoding="utf-8")


def test_summary_helper_uses_injected_task_facade_patch_seam():
    from api.task_route_summary import summarize_document_request

    db = MagicMock()
    catalog = MagicMock(
        content="City council meeting discussed budget updates and adopted multiple motions after public comment.",
        summary=None,
        summary_source_hash=None,
    )
    db.get.return_value = catalog
    facade = MagicMock()
    facade._summary_doc_kind_and_hashes.return_value = ("minutes", "content-hash", None)
    facade._enqueue_task.return_value = "summary-task"

    payload = summarize_document_request(
        task_facade=facade,
        db=db,
        catalog_id=123,
        force=False,
        catalog_model=MagicMock,
        analyze_source_text=lambda text: {"text": text},
        build_low_signal_message=lambda _quality: "low signal",
        is_summary_fresh=lambda *_args, **_kwargs: False,
        is_source_summarizable=lambda _quality: True,
    )

    assert payload == {"status": "processing", "task_id": "summary-task", "poll_url": "/tasks/summary-task"}
    facade._enqueue_task.assert_called_once_with(
        "generate_summary_task",
        facade.generate_summary_task,
        123,
        force=False,
    )


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

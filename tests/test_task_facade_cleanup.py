import sys
import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from kombu.exceptions import OperationalError

sys.modules["llama_cpp"] = MagicMock()


def test_summary_backfill_operation_is_not_exported_through_task_facades():
    from pipeline import task_facade_helpers, tasks

    obsolete_exports = (
        "_summary_doc_kind_subquery",
        "select_catalog_ids_for_summary_hydration",
        "_summary_doc_kind_map",
        "_enqueue_embed_catalogs",
        "run_summary_hydration_backfill",
    )

    for obsolete_export in obsolete_exports:
        assert not hasattr(task_facade_helpers, obsolete_export)
        assert not hasattr(tasks, obsolete_export)


def test_api_task_routes_do_not_export_dispatch_patch_points():
    from api import task_routes

    obsolete_exports = (
        "AsyncResult",
        "_CeleryTaskProxy",
        "_enqueue_task",
        "extract_text_task",
        "extract_votes_task",
        "generate_summary_task",
        "generate_topics_task",
        "segment_agenda_task",
    )

    for obsolete_export in obsolete_exports:
        assert not hasattr(task_routes, obsolete_export)


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


def test_failed_task_polling_returns_exception_message():
    from api.task_route_support import get_task_status_payload

    failed_task = MagicMock(ready=lambda: True, result=RuntimeError("worker failed"))
    task_id = "adf53fd7-c74f-401d-9cb2-b93332290550"

    with patch("api.task_route_support.AsyncResult", return_value=failed_task):
        payload = get_task_status_payload(task_id)

    assert payload == {"status": "failed", "error": "worker failed"}


def test_failed_task_polling_returns_structured_error():
    from api.task_route_support import get_task_status_payload

    failed_task = MagicMock(ready=lambda: True, result={"error": "provider unavailable"})
    task_id = "2a836b3e-3786-42a0-87da-ad834729f0a1"

    with patch("api.task_route_support.AsyncResult", return_value=failed_task):
        payload = get_task_status_payload(task_id)

    assert payload == {"status": "failed", "error": "provider unavailable"}


def test_task_dispatch_logs_stable_operation_key(caplog):
    from api.task_dispatch import enqueue_task

    with caplog.at_level(logging.ERROR, logger="town-council-api"), patch(
        "api.task_dispatch.celery_app.send_task",
        side_effect=OperationalError("broker down"),
    ):
        with pytest.raises(HTTPException) as exc_info:
            enqueue_task(
                "generate_summary_task",
                "pipeline.tasks.generate_summary_task",
                123,
                force=False,
            )

    assert exc_info.value.status_code == 503
    assert caplog.records[-1].task_name == "generate_summary_task"

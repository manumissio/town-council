import ast
import sys
import inspect
import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from kombu.exceptions import OperationalError

sys.modules["llama_cpp"] = MagicMock()


def test_task_facade_helper_module_is_deleted():
    from pipeline import tasks

    obsolete_exports = (
        "_summary_doc_kind_subquery",
        "select_catalog_ids_for_summary_hydration",
        "_summary_doc_kind_map",
        "_enqueue_embed_catalogs",
        "run_summary_hydration_backfill",
    )

    for obsolete_export in obsolete_exports:
        assert not hasattr(tasks, obsolete_export)



def _celery_task_source_contract(
    tasks_path: Path,
    task_name: str,
) -> tuple[bool, int, tuple[int, ...]]:
    tasks_tree = ast.parse(tasks_path.read_text(encoding="utf-8"))
    task_function = next(
        node
        for node in tasks_tree.body
        if isinstance(node, ast.FunctionDef) and node.name == task_name
    )
    task_decorator = next(
        decorator
        for decorator in task_function.decorator_list
        if isinstance(decorator, ast.Call)
        and isinstance(decorator.func, ast.Attribute)
        and decorator.func.attr == "task"
    )
    decorator_values = {
        keyword.arg: keyword.value.value
        for keyword in task_decorator.keywords
        if keyword.arg is not None and isinstance(keyword.value, ast.Constant)
    }
    retry_countdowns = tuple(
        keyword.value.value
        for call in ast.walk(task_function)
        if isinstance(call, ast.Call)
        and isinstance(call.func, ast.Attribute)
        and call.func.attr == "retry"
        for keyword in call.keywords
        if keyword.arg == "countdown" and isinstance(keyword.value, ast.Constant)
    )
    return bool(decorator_values["bind"]), int(decorator_values["max_retries"]), retry_countdowns


def test_celery_task_contracts_remain_stable():
    from pipeline import tasks

    task_contracts = {
        "generate_summary_task": (
            "pipeline.tasks.generate_summary_task",
            3,
            {"catalog_id": inspect.Parameter.empty, "force": False},
            (60,),
        ),
        "segment_agenda_task": (
            "pipeline.tasks.segment_agenda_task",
            3,
            {"catalog_id": inspect.Parameter.empty},
            (60,),
        ),
        "extract_votes_task": (
            "pipeline.tasks.extract_votes_task",
            3,
            {"catalog_id": inspect.Parameter.empty, "force": False},
            (60,),
        ),
        "extract_text_task": (
            "pipeline.tasks.extract_text_task",
            3,
            {
                "catalog_id": inspect.Parameter.empty,
                "force": False,
                "ocr_fallback": False,
            },
            (60,),
        ),
        "compute_lineage_task": (
            "pipeline.tasks.compute_lineage_task",
            3,
            {},
            (30,),
        ),
        "compute_lineage_for_catalog_task": (
            "pipeline.tasks.compute_lineage_for_catalog_task",
            1,
            {"catalog_id": inspect.Parameter.empty},
            (),
        ),
    }

    tasks_path = Path(tasks.__file__)
    for task_name, (registered_name, max_retries, parameter_defaults, retry_countdowns) in task_contracts.items():
        celery_task = getattr(tasks, task_name)
        assert celery_task.name == registered_name
        assert celery_task.max_retries == max_retries
        run_parameters = inspect.signature(celery_task.run).parameters
        assert {name: parameter.default for name, parameter in run_parameters.items()} == parameter_defaults
        assert _celery_task_source_contract(tasks_path, task_name) == (True, max_retries, retry_countdowns)


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

import importlib.util
from pathlib import Path


spec = importlib.util.spec_from_file_location("parse_task_launch", Path("scripts/parse_task_launch.py"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_parse_launch_response_accepts_uuid_task_id():
    parsed = mod.parse_launch_response(
        '{"task_id":"123e4567-e89b-12d3-a456-426614174000","status":"processing"}'
    )

    assert parsed["task_id"] == "123e4567-e89b-12d3-a456-426614174000"
    assert parsed["task_id_valid"] is True
    assert parsed["status"] == "processing"
    assert parsed["detail"] == ""


def test_parse_launch_response_rejects_error_detail_as_task_id():
    parsed = mod.parse_launch_response('{"detail":"Internal Server Error"}')

    assert parsed["task_id"] == ""
    assert parsed["task_id_valid"] is False
    assert parsed["status"] == ""
    assert parsed["detail"] == "Internal Server Error"


def test_parse_launch_response_rejects_non_uuid_task_id():
    parsed = mod.parse_launch_response('{"task_id":"Internal","status":"processing"}')

    assert parsed["task_id"] == ""
    assert parsed["task_id_valid"] is False
    assert parsed["status"] == "processing"

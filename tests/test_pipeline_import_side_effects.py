import importlib
import sys

import pytest
import sqlalchemy


@pytest.mark.parametrize(
    "module_name",
    [
        "pipeline.models",
        "pipeline.tasks",
        "pipeline.verification_service",
    ],
)
def test_pipeline_modules_do_not_connect_to_db_on_import(monkeypatch, module_name):
    calls = []
    real_create_engine = sqlalchemy.create_engine

    def tracking_create_engine(*args, **kwargs):
        calls.append((args, kwargs))
        return real_create_engine(*args, **kwargs)

    monkeypatch.setattr(sqlalchemy, "create_engine", tracking_create_engine)
    sys.modules.pop(module_name, None)

    importlib.import_module(module_name)

    assert calls == []

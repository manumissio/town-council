import importlib
import sys

import pytest
import sqlalchemy
import logging


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


@pytest.mark.parametrize(
    "module_name",
    [
        "pipeline.downloader",
        "pipeline.backfill_catalog_hashes",
        "pipeline.extractor",
        "pipeline.verification_service",
    ],
)
def test_reusable_pipeline_modules_do_not_configure_logging_on_import(monkeypatch, module_name):
    recorded_calls = []

    def tracking_basicconfig(*args, **kwargs):
        recorded_calls.append((args, kwargs))

    monkeypatch.setattr(logging, "basicConfig", tracking_basicconfig)
    sys.modules.pop(module_name, None)

    importlib.import_module(module_name)

    assert recorded_calls == []

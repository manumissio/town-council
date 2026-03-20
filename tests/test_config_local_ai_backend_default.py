import importlib

import pipeline.config as config_mod


def test_local_ai_backend_defaults_to_http_when_unset(monkeypatch):
    monkeypatch.delenv("LOCAL_AI_BACKEND", raising=False)
    reloaded = importlib.reload(config_mod)
    assert reloaded.LOCAL_AI_BACKEND == "http"


def test_local_ai_backend_invalid_value_normalizes_to_http(monkeypatch):
    monkeypatch.setenv("LOCAL_AI_BACKEND", "bogus")
    reloaded = importlib.reload(config_mod)
    assert reloaded.LOCAL_AI_BACKEND == "http"

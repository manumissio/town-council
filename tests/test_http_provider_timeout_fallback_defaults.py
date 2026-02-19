import importlib


def test_split_timeouts_fallback_to_global_when_unset(monkeypatch):
    monkeypatch.setenv("LOCAL_AI_HTTP_TIMEOUT_SECONDS", "77")
    monkeypatch.delenv("LOCAL_AI_HTTP_TIMEOUT_SEGMENT_SECONDS", raising=False)
    monkeypatch.delenv("LOCAL_AI_HTTP_TIMEOUT_SUMMARY_SECONDS", raising=False)
    monkeypatch.delenv("LOCAL_AI_HTTP_TIMEOUT_TOPICS_SECONDS", raising=False)

    import pipeline.config as config_module

    config_module = importlib.reload(config_module)

    assert config_module.LOCAL_AI_HTTP_TIMEOUT_SECONDS == 77
    assert config_module.LOCAL_AI_HTTP_TIMEOUT_SEGMENT_SECONDS == 77
    assert config_module.LOCAL_AI_HTTP_TIMEOUT_SUMMARY_SECONDS == 77
    assert config_module.LOCAL_AI_HTTP_TIMEOUT_TOPICS_SECONDS == 77

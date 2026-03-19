import requests

from pipeline.llm_provider import HttpInferenceProvider, ProviderTimeoutError


def test_extract_agenda_uses_zero_http_retries(monkeypatch):
    provider = HttpInferenceProvider()
    attempts = {"count": 0}

    def _always_timeout(*_args, **_kwargs):
        attempts["count"] += 1
        raise requests.exceptions.Timeout("timed out")

    monkeypatch.setattr("pipeline.llm_provider.requests.post", _always_timeout)

    try:
        provider.extract_agenda("prompt", temperature=0.1, max_tokens=64)
    except ProviderTimeoutError:
        pass
    else:  # pragma: no cover - defensive
        raise AssertionError("expected ProviderTimeoutError")

    assert attempts["count"] == 1


def test_summarize_agenda_items_keeps_configured_retry_budget(monkeypatch):
    provider = HttpInferenceProvider()
    attempts = {"count": 0}

    def _always_timeout(*_args, **_kwargs):
        attempts["count"] += 1
        raise requests.exceptions.Timeout("timed out")

    monkeypatch.setattr("pipeline.llm_provider.requests.post", _always_timeout)

    try:
        provider.summarize_agenda_items("prompt", temperature=0.1, max_tokens=64)
    except ProviderTimeoutError:
        pass
    else:  # pragma: no cover - defensive
        raise AssertionError("expected ProviderTimeoutError")

    assert attempts["count"] == provider.max_retries + 1

import requests

from pipeline.llm_provider import HttpInferenceProvider, ProviderTimeoutError


def test_http_provider_timeout_emits_retry_and_timeout(monkeypatch):
    events = {"timeout": 0, "retry": 0, "request": 0}

    monkeypatch.setattr("pipeline.llm_provider.record_provider_timeout", lambda *args, **kwargs: events.__setitem__("timeout", events["timeout"] + 1))
    monkeypatch.setattr("pipeline.llm_provider.record_provider_retry", lambda *args, **kwargs: events.__setitem__("retry", events["retry"] + 1))
    monkeypatch.setattr("pipeline.llm_provider.record_provider_request", lambda *args, **kwargs: events.__setitem__("request", events["request"] + 1))

    monkeypatch.setattr(
        requests,
        "post",
        lambda *args, **kwargs: (_ for _ in ()).throw(requests.exceptions.Timeout("slow")),
    )

    provider = HttpInferenceProvider()
    provider.max_retries = 2

    try:
        provider.summarize_text("hello", temperature=0.1, max_tokens=16)
    except ProviderTimeoutError:
        pass
    else:
        raise AssertionError("expected ProviderTimeoutError")

    assert events["timeout"] == 3
    assert events["retry"] == 2
    assert events["request"] == 3

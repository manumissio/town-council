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


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_http_provider_missing_stats_skips_token_metrics(monkeypatch):
    events = {"ttft": 0, "tps": 0, "tokens": 0, "request": 0}

    monkeypatch.setattr(
        "pipeline.llm_provider.record_provider_request",
        lambda *args, **kwargs: events.__setitem__("request", events["request"] + 1),
    )
    monkeypatch.setattr(
        "pipeline.llm_provider.record_provider_ttft",
        lambda *args, **kwargs: events.__setitem__("ttft", events["ttft"] + 1),
    )
    monkeypatch.setattr(
        "pipeline.llm_provider.record_provider_tokens_per_sec",
        lambda *args, **kwargs: events.__setitem__("tps", events["tps"] + 1),
    )
    monkeypatch.setattr(
        "pipeline.llm_provider.record_provider_token_counts",
        lambda *args, **kwargs: events.__setitem__("tokens", events["tokens"] + 1),
    )
    monkeypatch.setattr(
        requests,
        "post",
        lambda *args, **kwargs: _FakeResponse({"response": "ok"}),
    )

    provider = HttpInferenceProvider()
    out = provider.summarize_text("hello", temperature=0.1, max_tokens=16)
    assert out == "ok"
    assert events["request"] == 1
    assert events["ttft"] == 0
    assert events["tps"] == 0
    assert events["tokens"] == 0

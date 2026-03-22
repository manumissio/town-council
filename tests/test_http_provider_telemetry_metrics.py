import pytest
import requests

import pipeline.llm_provider as llm_provider
from pipeline.llm_provider import HttpInferenceProvider, ProviderResponseError, ProviderTimeoutError


def test_http_provider_timeout_emits_single_attempt_metrics_in_conservative_profile(monkeypatch):
    events = {"timeout": 0, "retry": 0, "request": 0}

    monkeypatch.setattr(llm_provider, "LOCAL_AI_HTTP_PROFILE", "conservative")
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

    assert events["timeout"] == 1
    assert events["retry"] == 0
    assert events["request"] == 1


def test_http_provider_timeout_emits_retry_metrics_in_balanced_profile(monkeypatch):
    events = {"timeout": 0, "retry": 0, "request": 0}

    monkeypatch.setattr(llm_provider, "LOCAL_AI_HTTP_PROFILE", "balanced")
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

    with pytest.raises(ProviderTimeoutError):
        provider.summarize_text("hello", temperature=0.1, max_tokens=16)

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


def test_http_provider_empty_response_payload_is_response_error_without_retry(monkeypatch):
    events = {"retry": 0, "request": 0}

    monkeypatch.setattr("pipeline.llm_provider.record_provider_retry", lambda *args, **kwargs: events.__setitem__("retry", events["retry"] + 1))
    monkeypatch.setattr("pipeline.llm_provider.record_provider_request", lambda *args, **kwargs: events.__setitem__("request", events["request"] + 1))

    monkeypatch.setattr(
        requests,
        "post",
        lambda *args, **kwargs: _FakeResponse({"response": "   "}),
    )

    provider = HttpInferenceProvider()
    provider.max_retries = 3
    with pytest.raises(ProviderResponseError):
        provider.summarize_text("hello", temperature=0.1, max_tokens=16)

    # Deterministic response-shape failure should not trigger transport retries.
    assert events["retry"] == 0
    assert events["request"] == 1


def test_http_provider_invalid_json_is_response_error_without_retry(monkeypatch):
    events = {"retry": 0}

    class _BadJsonResponse:
        def raise_for_status(self):
            return None

        def json(self):
            raise ValueError("bad json")

    monkeypatch.setattr("pipeline.llm_provider.record_provider_retry", lambda *args, **kwargs: events.__setitem__("retry", events["retry"] + 1))
    monkeypatch.setattr(requests, "post", lambda *args, **kwargs: _BadJsonResponse())

    provider = HttpInferenceProvider()
    provider.max_retries = 2
    with pytest.raises(ProviderResponseError):
        provider.summarize_text("hello", temperature=0.1, max_tokens=16)

    assert events["retry"] == 0

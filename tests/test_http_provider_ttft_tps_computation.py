import requests

from pipeline.llm_provider import HttpInferenceProvider


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_http_provider_omits_tps_when_eval_duration_is_zero(monkeypatch):
    seen = {"ttft": 0, "tps": 0, "tokens": None}

    payload = {
        "response": "ok",
        "prompt_eval_count": 10,
        "eval_count": 20,
        "prompt_eval_duration": 1_000_000_000,
        "eval_duration": 0,
    }

    monkeypatch.setattr(requests, "post", lambda *args, **kwargs: _FakeResponse(payload))
    monkeypatch.setattr("pipeline.llm_provider.record_provider_request", lambda *args, **kwargs: None)
    monkeypatch.setattr("pipeline.llm_provider.record_provider_timeout", lambda *args, **kwargs: None)
    monkeypatch.setattr("pipeline.llm_provider.record_provider_retry", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        "pipeline.llm_provider.record_provider_ttft",
        lambda *args, **kwargs: seen.__setitem__("ttft", seen["ttft"] + 1),
    )
    monkeypatch.setattr(
        "pipeline.llm_provider.record_provider_tokens_per_sec",
        lambda *args, **kwargs: seen.__setitem__("tps", seen["tps"] + 1),
    )
    monkeypatch.setattr(
        "pipeline.llm_provider.record_provider_token_counts",
        lambda provider, operation, model, outcome, prompt_tokens, completion_tokens: seen.__setitem__(
            "tokens", (prompt_tokens, completion_tokens)
        ),
    )

    provider = HttpInferenceProvider()
    text = provider.summarize_text("hello", temperature=0.1, max_tokens=64)
    assert text == "ok"
    assert seen["ttft"] == 1
    assert seen["tps"] == 0
    assert seen["tokens"] == (10, 20)

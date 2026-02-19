import requests

from pipeline.llm_provider import HttpInferenceProvider


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_http_provider_emits_token_metrics_when_stats_exist(monkeypatch):
    seen = {"counts": None, "ttft": None, "tps": None}

    payload = {
        "response": "ok",
        "prompt_eval_count": 123,
        "eval_count": 45,
        "prompt_eval_duration": 2_500_000_000,
        "eval_duration": 3_000_000_000,
    }

    monkeypatch.setattr(requests, "post", lambda *args, **kwargs: _FakeResponse(payload))
    monkeypatch.setattr("pipeline.llm_provider.record_provider_request", lambda *args, **kwargs: None)
    monkeypatch.setattr("pipeline.llm_provider.record_provider_timeout", lambda *args, **kwargs: None)
    monkeypatch.setattr("pipeline.llm_provider.record_provider_retry", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        "pipeline.llm_provider.record_provider_ttft",
        lambda provider, operation, model, outcome, ttft_ms: seen.__setitem__("ttft", ttft_ms),
    )
    monkeypatch.setattr(
        "pipeline.llm_provider.record_provider_tokens_per_sec",
        lambda provider, operation, model, outcome, tokens_per_sec: seen.__setitem__("tps", tokens_per_sec),
    )
    monkeypatch.setattr(
        "pipeline.llm_provider.record_provider_token_counts",
        lambda provider, operation, model, outcome, prompt_tokens, completion_tokens: seen.__setitem__(
            "counts", (prompt_tokens, completion_tokens)
        ),
    )

    provider = HttpInferenceProvider()
    text = provider.summarize_text("hello", temperature=0.1, max_tokens=64)
    assert text == "ok"
    assert seen["counts"] == (123, 45)
    assert seen["ttft"] == 2500.0
    assert seen["tps"] == 15.0

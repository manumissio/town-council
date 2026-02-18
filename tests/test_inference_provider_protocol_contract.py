import threading

from pipeline.llm_provider import InferenceProvider, InProcessLlamaProvider, HttpInferenceProvider


class _DummyLlama:
    def __call__(self, prompt, max_tokens=0, temperature=0.0, response_format=None):
        _ = (prompt, max_tokens, temperature, response_format)
        return {"choices": [{"text": "ok"}]}

    def reset(self):
        return None


class _DummyOwner:
    def __init__(self):
        self._lock = threading.Lock()
        self.llm = _DummyLlama()

    def _load_model(self):
        return None


def test_inprocess_provider_satisfies_protocol():
    provider = InProcessLlamaProvider(_DummyOwner())
    assert isinstance(provider, InferenceProvider)
    assert provider.summarize_text("x", temperature=0.0, max_tokens=8) == "ok"


def test_http_provider_has_protocol_methods():
    provider = HttpInferenceProvider()
    assert isinstance(provider, InferenceProvider)
    assert hasattr(provider, "extract_agenda")
    assert hasattr(provider, "summarize_agenda_items")
    assert hasattr(provider, "summarize_text")
    assert hasattr(provider, "generate_topics")

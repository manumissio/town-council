import threading

from pipeline import llm as llm_mod
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


def test_local_ai_defaults_to_http_provider_when_backend_unset(monkeypatch):
    llm_mod.LocalAI._instance = None
    monkeypatch.setattr(llm_mod, "LOCAL_AI_BACKEND", "")
    ai = llm_mod.LocalAI()
    provider = ai._get_provider()
    assert isinstance(provider, HttpInferenceProvider)


def test_local_ai_invalid_backend_normalizes_to_http_provider(monkeypatch):
    llm_mod.LocalAI._instance = None
    monkeypatch.setattr(llm_mod, "LOCAL_AI_BACKEND", "bogus")
    ai = llm_mod.LocalAI()
    provider = ai._get_provider()
    assert isinstance(provider, HttpInferenceProvider)

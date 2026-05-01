import threading

from pipeline import llm as llm_mod
from pipeline.llm_provider import InferenceProvider, InProcessLlamaProvider, HttpInferenceProvider
from pipeline.llm_provider import ProviderResponseError


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


class _FormatRejectingLlama:
    def __init__(self):
        self.reset_count = 0

    def __call__(self, prompt, max_tokens=0, temperature=0.0, response_format=None):
        _ = (prompt, max_tokens, temperature)
        if response_format is not None:
            raise TypeError("response_format not supported")
        return {"choices": [{"text": "json ok"}]}

    def reset(self):
        self.reset_count += 1


class _FailingLlama:
    def __init__(self):
        self.reset_count = 0

    def __call__(self, prompt, max_tokens=0, temperature=0.0, response_format=None):
        _ = (prompt, max_tokens, temperature, response_format)
        raise RuntimeError("model failed")

    def reset(self):
        self.reset_count += 1


class _AssertionFailingLlama:
    def __init__(self):
        self.reset_count = 0

    def __call__(self, prompt, max_tokens=0, temperature=0.0, response_format=None):
        _ = (prompt, max_tokens, temperature, response_format)
        raise AssertionError("model assertion failed")

    def reset(self):
        self.reset_count += 1


class _MemoryFailingLlama:
    def __init__(self):
        self.reset_count = 0

    def __call__(self, prompt, max_tokens=0, temperature=0.0, response_format=None):
        _ = (prompt, max_tokens, temperature, response_format)
        raise MemoryError("model memory failed")

    def reset(self):
        self.reset_count += 1


class _OsFailingLlama:
    def __init__(self):
        self.reset_count = 0

    def __call__(self, prompt, max_tokens=0, temperature=0.0, response_format=None):
        _ = (prompt, max_tokens, temperature, response_format)
        raise OSError("model os failed")

    def reset(self):
        self.reset_count += 1


def test_inprocess_provider_satisfies_protocol():
    provider = InProcessLlamaProvider(_DummyOwner())
    assert isinstance(provider, InferenceProvider)
    assert provider.summarize_text("x", temperature=0.0, max_tokens=8) == "ok"


def test_inprocess_provider_preserves_response_format_fallback():
    owner = _DummyOwner()
    owner.llm = _FormatRejectingLlama()
    provider = InProcessLlamaProvider(owner)

    assert provider.generate_json("{}", max_tokens=8) == "json ok"
    assert owner.llm.reset_count == 1


def test_inprocess_provider_maps_backend_failure_and_resets_model():
    owner = _DummyOwner()
    owner.llm = _FailingLlama()
    provider = InProcessLlamaProvider(owner)

    try:
        provider.summarize_text("x", temperature=0.0, max_tokens=8)
    except ProviderResponseError:
        pass
    else:  # pragma: no cover - defensive
        raise AssertionError("expected ProviderResponseError")

    assert owner.llm.reset_count == 1


def test_inprocess_provider_maps_model_assertion_failure_to_response_error():
    owner = _DummyOwner()
    owner.llm = _AssertionFailingLlama()
    provider = InProcessLlamaProvider(owner)

    try:
        provider.summarize_agenda_items("x", temperature=0.0, max_tokens=8)
    except ProviderResponseError:
        pass
    else:  # pragma: no cover - defensive
        raise AssertionError("expected ProviderResponseError")

    assert owner.llm.reset_count == 1


def test_inprocess_provider_maps_model_memory_failure_to_response_error():
    owner = _DummyOwner()
    owner.llm = _MemoryFailingLlama()
    provider = InProcessLlamaProvider(owner)

    try:
        provider.summarize_agenda_items("x", temperature=0.0, max_tokens=8)
    except ProviderResponseError:
        pass
    else:  # pragma: no cover - defensive
        raise AssertionError("expected ProviderResponseError")

    assert owner.llm.reset_count == 1


def test_inprocess_provider_maps_model_os_failure_to_response_error():
    owner = _DummyOwner()
    owner.llm = _OsFailingLlama()
    provider = InProcessLlamaProvider(owner)

    try:
        provider.summarize_agenda_items("x", temperature=0.0, max_tokens=8)
    except ProviderResponseError:
        pass
    else:  # pragma: no cover - defensive
        raise AssertionError("expected ProviderResponseError")

    assert owner.llm.reset_count == 1


def test_http_provider_has_protocol_methods():
    provider = HttpInferenceProvider()
    assert isinstance(provider, InferenceProvider)
    assert hasattr(provider, "extract_agenda")
    assert hasattr(provider, "summarize_agenda_items")
    assert hasattr(provider, "summarize_text")
    assert hasattr(provider, "generate_topics")
    assert hasattr(provider, "generate_json")


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

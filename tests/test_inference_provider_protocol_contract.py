import threading

from pipeline import llm as llm_mod
from pipeline import llm_provider
from pipeline.http_inference_payloads import parse_openai_compatible_response_payload
from pipeline.http_inference_provider import HttpInferenceProvider as DirectHttpInferenceProvider
from pipeline.llm_provider import InferenceProvider, InProcessLlamaProvider, HttpInferenceProvider
from pipeline.llm_provider import ProviderResponseError
from pipeline.provider_telemetry import TOKEN_METRIC_COMPLETION_TOKENS, TOKEN_METRIC_PROMPT_TOKENS


class _JsonResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class _OkResponse:
    ok = True


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


def test_http_provider_payload_includes_configured_context_window(monkeypatch):
    monkeypatch.setattr(llm_provider, "LOCAL_AI_HTTP_API", "ollama")
    monkeypatch.setattr(llm_provider, "LLM_CONTEXT_WINDOW", 8192)
    provider = DirectHttpInferenceProvider()

    payload = provider._build_request_payload("summarize this", max_tokens=128, temperature=0.2)

    assert payload["options"]["num_ctx"] == 8192
    assert payload["options"]["num_predict"] == 128
    assert payload["options"]["temperature"] == 0.2


def test_http_provider_openai_compatible_payload_uses_chat_completion_shape(monkeypatch):
    monkeypatch.setattr(llm_provider, "LOCAL_AI_HTTP_API", "openai_compat")
    monkeypatch.setattr(llm_provider, "LOCAL_AI_HTTP_MODEL", "mlx-community/test-model")
    provider = DirectHttpInferenceProvider()

    payload = provider._build_request_payload("summarize this", max_tokens=128, temperature=0.2)

    assert payload == {
        "model": "mlx-community/test-model",
        "messages": [{"role": "user", "content": "summarize this"}],
        "temperature": 0.2,
        "max_tokens": 128,
        "stream": False,
    }


def test_http_provider_openai_compatible_health_check_uses_health_endpoint(monkeypatch):
    requested_urls = []

    def fake_get(url, timeout):
        requested_urls.append((url, timeout))
        return _OkResponse()

    monkeypatch.setattr(llm_provider, "LOCAL_AI_HTTP_API", "openai_compat")
    monkeypatch.setattr(llm_provider, "LOCAL_AI_HTTP_BASE_URL", "http://host.docker.internal:8080")
    monkeypatch.setattr(llm_provider.requests, "get", fake_get)
    provider = DirectHttpInferenceProvider()

    assert provider.health_check() is True
    assert requested_urls[0][0] == "http://host.docker.internal:8080/health"


def test_openai_compatible_response_parser_returns_content_and_usage_tokens():
    text, token_metrics = parse_openai_compatible_response_payload(
        _JsonResponse(
            {
                "choices": [{"message": {"content": "  useful summary  "}}],
                "usage": {"prompt_tokens": 11, "completion_tokens": 7},
            }
        )
    )

    assert text == "useful summary"
    assert token_metrics[TOKEN_METRIC_PROMPT_TOKENS] == 11
    assert token_metrics[TOKEN_METRIC_COMPLETION_TOKENS] == 7


def test_openai_compatible_response_parser_rejects_empty_choices():
    try:
        parse_openai_compatible_response_payload(_JsonResponse({"choices": []}))
    except ProviderResponseError:
        pass
    else:  # pragma: no cover - defensive
        raise AssertionError("expected ProviderResponseError")


def test_openai_compatible_response_parser_rejects_missing_content():
    try:
        parse_openai_compatible_response_payload(_JsonResponse({"choices": [{"message": {}}]}))
    except ProviderResponseError:
        pass
    else:  # pragma: no cover - defensive
        raise AssertionError("expected ProviderResponseError")


def test_openai_compatible_response_parser_rejects_empty_content():
    try:
        parse_openai_compatible_response_payload(_JsonResponse({"choices": [{"message": {"content": "  "}}]}))
    except ProviderResponseError:
        pass
    else:  # pragma: no cover - defensive
        raise AssertionError("expected ProviderResponseError")


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


def test_http_provider_import_contract_preserves_llm_provider_facade():
    assert llm_provider.HttpInferenceProvider is DirectHttpInferenceProvider
    assert HttpInferenceProvider is DirectHttpInferenceProvider


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

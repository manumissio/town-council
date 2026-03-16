import pytest


def test_local_ai_refuses_multiprocess_by_default(monkeypatch):
    """
    LocalAI should fail fast when the configured worker runtime would duplicate the
    in-process model across multiple processes.
    """
    import pipeline.llm as llm

    # Ensure singleton state doesn't leak across tests.
    llm.LocalAI._instance = None

    monkeypatch.setattr(llm, "LOCAL_AI_BACKEND", "inprocess")
    monkeypatch.setattr(llm, "LOCAL_AI_ALLOW_MULTIPROCESS", False)
    monkeypatch.setattr(llm, "LOCAL_AI_REQUIRE_SOLO_POOL", True)
    monkeypatch.setattr(llm, "local_ai_guardrail_inputs_from_env", lambda: (4, "prefork"))

    with pytest.raises(llm.LocalAIConfigError):
        llm.LocalAI()._load_model()


def test_local_ai_allows_http_backend_even_with_prefork_inputs(monkeypatch):
    import pipeline.llm as llm

    llm.LocalAI._instance = None

    monkeypatch.setattr(llm, "LOCAL_AI_BACKEND", "http")
    monkeypatch.setattr(llm, "LOCAL_AI_ALLOW_MULTIPROCESS", False)
    monkeypatch.setattr(llm, "LOCAL_AI_REQUIRE_SOLO_POOL", True)
    monkeypatch.setattr(llm, "local_ai_guardrail_inputs_from_env", lambda: (4, "prefork"))

    llm.LocalAI()._load_model()

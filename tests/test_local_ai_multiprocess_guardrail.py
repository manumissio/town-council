import pytest


def test_local_ai_refuses_multiprocess_by_default(monkeypatch):
    """
    LocalAI loads a GGUF model into the current *process*.
    If we detect a non-main process (Celery prefork), we must fail fast by default.
    """
    import pipeline.llm as llm

    # Ensure singleton state doesn't leak across tests.
    llm.LocalAI._instance = None

    monkeypatch.setattr(llm, "LOCAL_AI_ALLOW_MULTIPROCESS", False)

    class _Proc:
        name = "ForkPoolWorker-1"

    monkeypatch.setattr(llm.multiprocessing, "current_process", lambda: _Proc())

    with pytest.raises(llm.LocalAIConfigError):
        llm.LocalAI()._load_model()


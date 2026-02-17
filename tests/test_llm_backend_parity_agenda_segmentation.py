import sys
from unittest.mock import MagicMock

sys.modules.setdefault("llama_cpp", MagicMock())


def _reset_local_ai_singleton():
    from pipeline.llm import LocalAI

    LocalAI._instance = None


def _fake_agenda_text(_self, prompt, max_tokens, temperature, response_format=None):
    _ = (prompt, max_tokens, temperature, response_format)
    return (
        "Housing rezoning proposal (Page 2) - Consider zoning amendments.\n"
        "ITEM 2: Budget adoption (Page 3) - Adopt annual budget."
    )


def _run(backend, monkeypatch):
    from pipeline import llm as llm_mod

    monkeypatch.setattr(llm_mod, "LOCAL_AI_BACKEND", backend)
    monkeypatch.setattr(llm_mod.InProcessLlamaProvider, "generate", _fake_agenda_text)
    monkeypatch.setattr(llm_mod.HttpInferenceProvider, "generate", _fake_agenda_text)
    _reset_local_ai_singleton()

    ai = llm_mod.LocalAI()
    return ai.extract_agenda("[PAGE 2]\nAgenda text placeholder")


def test_backend_parity_agenda_segmentation(monkeypatch):
    inprocess = _run("inprocess", monkeypatch)
    http = _run("http", monkeypatch)

    assert inprocess == http
    assert len(inprocess) >= 1
    assert (inprocess[0].get("title") or "").strip()

import sys
from unittest.mock import MagicMock

sys.modules.setdefault("llama_cpp", MagicMock())


def _reset_local_ai_singleton():
    from pipeline.llm import LocalAI

    LocalAI._instance = None


def test_extract_agenda_truncates_prompt_to_agenda_budget(monkeypatch):
    from pipeline import llm as llm_mod

    captured = {}

    def _fake_extract(_self, prompt, *, temperature, max_tokens):
        captured["prompt"] = prompt
        return "Budget Review (Page 1) - Fiscal discussion"

    monkeypatch.setattr(llm_mod, "LOCAL_AI_BACKEND", "http")
    monkeypatch.setattr(llm_mod, "LLM_AGENDA_MAX_TEXT", 40)
    monkeypatch.setattr(llm_mod.HttpInferenceProvider, "extract_agenda", _fake_extract)
    _reset_local_ai_singleton()

    ai = llm_mod.LocalAI()
    items = ai.extract_agenda("A" * 40 + "B" * 20)

    assert items
    assert "A" * 40 in captured["prompt"]
    assert "B" * 20 not in captured["prompt"]


def test_extract_agenda_provider_timeout_falls_back_to_heuristics(monkeypatch):
    from pipeline import llm as llm_mod

    monkeypatch.setattr(llm_mod, "LOCAL_AI_BACKEND", "http")

    def _timeout(*_args, **_kwargs):
        raise llm_mod.ProviderTimeoutError("timed out")

    monkeypatch.setattr(llm_mod.HttpInferenceProvider, "extract_agenda", _timeout)
    _reset_local_ai_singleton()

    ai = llm_mod.LocalAI()
    items = ai.extract_agenda(
        "[PAGE 1]\n\n1. Budget Hearing\nAction: Approve annual budget.\n"
    )

    assert items
    assert items[0]["title"] == "Budget Hearing"

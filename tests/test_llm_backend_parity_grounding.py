import sys
from unittest.mock import MagicMock

sys.modules.setdefault("llama_cpp", MagicMock())


def _reset_local_ai_singleton():
    from pipeline.llm import LocalAI

    LocalAI._instance = None


def _fake_grounded_text(_self, prompt, max_tokens, temperature, response_format=None):
    _ = (prompt, max_tokens, temperature, response_format)
    return (
        "BLUF: Agenda includes 1 substantive item.\n"
        "Why this matters:\n"
        "- The meeting is focused on one decision.\n"
        "Top actions:\n"
        "- Approve paving contract (p.2)\n"
        "Potential impacts:\n"
        "- Budget: Potential fiscal impact is not clearly stated in the agenda text.\n"
        "- Policy: Policy/regulatory changes may be considered based on listed agenda items.\n"
        "- Process: The agenda indicates scheduled consideration; final outcomes are not yet available.\n"
        "Unknowns:\n"
        "- Specific dollar amounts are not clearly disclosed across the listed items."
    )


def _run(backend, monkeypatch):
    from pipeline import llm as llm_mod

    monkeypatch.setattr(llm_mod, "LOCAL_AI_BACKEND", backend)
    monkeypatch.setattr(llm_mod.InProcessLlamaProvider, "generate", _fake_grounded_text)
    monkeypatch.setattr(llm_mod.HttpInferenceProvider, "generate", _fake_grounded_text)
    _reset_local_ai_singleton()

    ai = llm_mod.LocalAI()
    return ai.summarize_agenda_items(
        meeting_title="City Council",
        meeting_date="2026-02-10",
        items=[
            {
                "title": "Approve paving contract",
                "description": "Approve a paving contract for arterial roads.",
                "page_number": 2,
                "classification": "Agenda Item",
                "result": "",
            }
        ],
    )


def test_backend_parity_grounding_path(monkeypatch):
    inprocess = _run("inprocess", monkeypatch)
    http = _run("http", monkeypatch)

    assert inprocess == http
    assert "Unknowns:" in (inprocess or "")

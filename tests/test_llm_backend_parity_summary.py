import sys
from unittest.mock import MagicMock

sys.modules.setdefault("llama_cpp", MagicMock())


def _reset_local_ai_singleton():
    from pipeline.llm import LocalAI

    LocalAI._instance = None


def _fake_summary_text(_self, prompt, max_tokens, temperature, response_format=None):
    _ = (prompt, max_tokens, temperature, response_format)
    return (
        "BLUF: Agenda includes major actions.\n"
        "Why this matters:\n"
        "- Policy and operational decisions are scheduled.\n"
        "Top actions:\n"
        "- Approve contract for paving.\n"
        "Potential impacts:\n"
        "- Budget: Funding implications may be significant.\n"
        "- Policy: Land-use rules may change.\n"
        "- Process: Formal votes are expected.\n"
        "Unknowns:\n"
        "- Vote outcomes are not yet available."
    )


def _run(backend, monkeypatch):
    from pipeline import llm as llm_mod

    monkeypatch.setattr(llm_mod, "LOCAL_AI_BACKEND", backend)
    monkeypatch.setattr(llm_mod.InProcessLlamaProvider, "generate", _fake_summary_text)
    monkeypatch.setattr(llm_mod.HttpInferenceProvider, "generate", _fake_summary_text)
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


def test_backend_parity_summary_structure(monkeypatch):
    inprocess = _run("inprocess", monkeypatch)
    http = _run("http", monkeypatch)

    assert inprocess == http
    lowered = (inprocess or "").lower()
    assert lowered.startswith("bluf:")
    assert "why this matters:" in lowered
    assert "top actions:" in lowered
    assert "potential impacts:" in lowered
    assert "unknowns:" in lowered

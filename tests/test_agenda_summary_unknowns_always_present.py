def test_summarize_agenda_items_always_has_unknowns_section(monkeypatch):
    from pipeline.llm import LocalAI

    class _FakeLLM:
        def __call__(self, prompt, max_tokens=0, temperature=0.0):
            # Too short/noncompliant -> deterministic fallback expected.
            return {"choices": [{"text": "BLUF: Short summary."}]}

        def reset(self):
            return None

    ai = LocalAI()
    monkeypatch.setattr(ai, "_load_model", lambda: setattr(ai, "llm", _FakeLLM()))
    summary = ai.summarize_agenda_items(
        meeting_title="Council",
        meeting_date="2026-02-10",
        items=[{"title": "Approve contract", "description": "Approve contract amendment.", "page_number": 1}],
    )
    assert "Unknowns:" in (summary or "")

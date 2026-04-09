def test_summarize_agenda_items_always_has_unknowns_section(monkeypatch):
    from pipeline.llm import LocalAI

    class _FakeProvider:
        def summarize_agenda_items(self, prompt, *, temperature, max_tokens):
            # Too short/noncompliant -> deterministic fallback expected.
            return "BLUF: Short summary."

    ai = LocalAI()
    monkeypatch.setattr(ai, "_get_provider", lambda: _FakeProvider())
    summary = ai.summarize_agenda_items(
        meeting_title="Council",
        meeting_date="2026-02-10",
        items=[{"title": "Approve contract", "description": "Approve contract amendment.", "page_number": 1}],
    )
    assert "Unknowns:" in (summary or "")

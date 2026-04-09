def test_summarize_agenda_items_prunes_unsupported_lines(monkeypatch):
    from pipeline.llm import LocalAI

    class _FakeProvider:
        def summarize_agenda_items(self, prompt, *, temperature, max_tokens):
            return (
                "BLUF: Agenda includes policy updates.\n"
                "Why this matters:\n"
                "- The council may adopt zoning amendments.\n"
                "Top actions:\n"
                "- Adopt zoning amendment for district standards.\n"
                "- Launch a lunar mining initiative next quarter.\n"
                "Potential impacts:\n"
                "- Budget: Not clearly stated.\n"
                "- Policy: Zoning rules may be updated.\n"
                "- Process: Formal review is scheduled.\n"
                "Unknowns:\n"
                "- Final vote outcomes are not yet available."
            )

    ai = LocalAI()
    monkeypatch.setattr(ai, "_get_provider", lambda: _FakeProvider())
    summary = ai.summarize_agenda_items(
        meeting_title="Planning Commission",
        meeting_date="2026-02-10",
        items=[{"title": "Adopt zoning amendment", "description": "Adopt zoning amendment for district standards.", "page_number": 2}],
    )
    lowered = (summary or "").lower()
    assert "lunar mining initiative" not in lowered
    assert "adopt zoning amendment" in lowered

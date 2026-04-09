def test_summarize_agenda_items_returns_sectioned_decision_brief(monkeypatch):
    from pipeline.llm import LocalAI

    class _FakeProvider:
        def summarize_agenda_items(self, prompt, *, temperature, max_tokens):
            return (
                "BLUF: Agenda includes major actions.\n"
                "Why this matters:\n"
                "- Policy and operational decisions are scheduled.\n"
                "Top actions:\n"
                "- Approve contract for paving.\n"
                "- Adopt zoning amendment.\n"
                "Potential impacts:\n"
                "- Budget: Funding implications may be significant.\n"
                "- Policy: Land-use rules may change.\n"
                "- Process: Formal votes are expected.\n"
                "Unknowns:\n"
                "- Vote outcomes are not yet available."
            )

    ai = LocalAI()
    monkeypatch.setattr(ai, "_get_provider", lambda: _FakeProvider())
    summary = ai.summarize_agenda_items(
        meeting_title="City Council",
        meeting_date="2026-02-10",
        items=[
            {"title": "Approve paving contract", "description": "Approve a paving contract for arterial roads.", "page_number": 2},
            {"title": "Adopt zoning amendment", "description": "Consider amendments to residential zoning standards.", "page_number": 3},
        ],
    )
    lowered = (summary or "").lower()
    assert lowered.startswith("bluf:")
    assert "why this matters:" in lowered
    assert "top actions:" in lowered
    assert "potential impacts:" in lowered
    assert "unknowns:" in lowered

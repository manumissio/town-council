def test_agenda_summary_uses_configured_temperature(monkeypatch):
    import pipeline.agenda_summary as agenda_summary_mod
    from pipeline.llm import LocalAI

    captured = {"temperature": None}

    class _FakeProvider:
        def summarize_agenda_items(self, prompt, *, temperature, max_tokens):
            captured["temperature"] = temperature
            return (
                "BLUF: Agenda includes substantive actions.\n"
                "Why this matters:\n"
                "- Decisions may influence city operations.\n"
                "Top actions:\n"
                "- Approve contract amendment.\n"
                "- Adopt ordinance update.\n"
                "Potential impacts:\n"
                "- Budget: Costs are under review.\n"
                "- Policy: Ordinance language may change.\n"
                "- Process: Formal votes are expected.\n"
                "Unknowns:\n"
                "- Final vote outcomes are not provided."
            )

    monkeypatch.setattr(agenda_summary_mod, "AGENDA_SUMMARY_TEMPERATURE", 0.37)
    ai = LocalAI()
    monkeypatch.setattr(ai, "_get_provider", lambda: _FakeProvider())
    summary = ai.summarize_agenda_items(
        meeting_title="Council",
        meeting_date="2026-02-10",
        items=[{"title": "Approve contract amendment", "description": "Contract terms update.", "page_number": 1}],
    )
    assert summary.startswith("BLUF:")
    assert captured["temperature"] == 0.37

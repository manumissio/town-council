def test_single_item_summary_includes_decision_action_section(monkeypatch):
    from pipeline.llm import LocalAI

    class _FakeProvider:
        def summarize_agenda_items(self, prompt, *, temperature, max_tokens):
            # Missing "Decision/action requested" on purpose; helper should inject it.
            return (
                "BLUF: Agenda includes 1 substantive item.\n"
                "Why this matters:\n"
                "- A single high-priority decision is scheduled.\n"
                "Top actions:\n"
                "- 2026 City Council Referral Prioritization Results Using Re-Weighted Range Voting (RRV)\n"
                "Potential impacts:\n"
                "- Budget: Not clearly stated.\n"
                "- Policy: Potential policy implications are present.\n"
                "- Process: Formal action may occur.\n"
                "Unknowns:\n"
                "- Vote outcomes are not provided."
            )

    ai = LocalAI()
    monkeypatch.setattr(ai, "_get_provider", lambda: _FakeProvider())
    summary = ai.summarize_agenda_items(
        meeting_title="Berkeley Special",
        meeting_date="2026-02-10",
        items=[{"title": "2026 City Council Referral Prioritization Results Using Re-Weighted Range Voting (RRV)", "description": "", "page_number": 2}],
    )
    lowered = (summary or "").lower()
    assert "decision/action requested:" in lowered

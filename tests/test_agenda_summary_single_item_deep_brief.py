def test_single_item_fallback_does_not_present_webinar_title_as_requested_action():
    from pipeline.agenda_summary_rendering import deterministic_agenda_items_summary

    title = "Less Traffic, Better Places: How Do We Get There?"
    summary = deterministic_agenda_items_summary(
        [{"title": title, "description": "Webinar registration and a sustainability presentation."}],
        max_bullets=25, truncation_meta=None, profile="decision_brief",
        min_item_desc_chars=20, single_item_mode="deep_brief",
    )
    decision_section = summary.split("Decision/action requested:", 1)[1].split("Potential impacts:", 1)[0]
    assert title in summary
    assert title not in decision_section
    assert "source" in decision_section.lower()


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

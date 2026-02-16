def test_single_item_summary_includes_decision_action_section(monkeypatch):
    from pipeline.llm import LocalAI

    class _FakeLLM:
        def __call__(self, prompt, max_tokens=0, temperature=0.0):
            # Missing "Decision/action requested" on purpose; helper should inject it.
            return {
                "choices": [{
                    "text": (
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
                }]
            }

        def reset(self):
            return None

    ai = LocalAI()
    monkeypatch.setattr(ai, "_load_model", lambda: setattr(ai, "llm", _FakeLLM()))
    summary = ai.summarize_agenda_items(
        meeting_title="Berkeley Special",
        meeting_date="2026-02-10",
        items=[{"title": "2026 City Council Referral Prioritization Results Using Re-Weighted Range Voting (RRV)", "description": "", "page_number": 2}],
    )
    lowered = (summary or "").lower()
    assert "decision/action requested:" in lowered

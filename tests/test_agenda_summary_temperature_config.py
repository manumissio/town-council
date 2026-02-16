def test_agenda_summary_uses_configured_temperature(monkeypatch):
    import pipeline.llm as llm_mod
    from pipeline.llm import LocalAI

    captured = {"temperature": None}

    class _FakeLLM:
        def __call__(self, prompt, max_tokens=0, temperature=0.0):
            captured["temperature"] = temperature
            return {
                "choices": [{
                    "text": (
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
                }]
            }

        def reset(self):
            return None

    monkeypatch.setattr(llm_mod, "AGENDA_SUMMARY_TEMPERATURE", 0.37)
    ai = LocalAI()
    monkeypatch.setattr(ai, "_load_model", lambda: setattr(ai, "llm", _FakeLLM()))
    summary = ai.summarize_agenda_items(
        meeting_title="Council",
        meeting_date="2026-02-10",
        items=[{"title": "Approve contract amendment", "description": "Contract terms update.", "page_number": 1}],
    )
    assert summary.startswith("BLUF:")
    assert captured["temperature"] == 0.37

def test_summarize_agenda_items_prunes_unsupported_lines(monkeypatch):
    from pipeline.llm import LocalAI

    class _FakeLLM:
        def __call__(self, prompt, max_tokens=0, temperature=0.0):
            return {
                "choices": [{
                    "text": (
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
                }]
            }

        def reset(self):
            return None

    ai = LocalAI()
    monkeypatch.setattr(ai, "_load_model", lambda: setattr(ai, "llm", _FakeLLM()))
    summary = ai.summarize_agenda_items(
        meeting_title="Planning Commission",
        meeting_date="2026-02-10",
        items=[{"title": "Adopt zoning amendment", "description": "Adopt zoning amendment for district standards.", "page_number": 2}],
    )
    lowered = (summary or "").lower()
    assert "lunar mining initiative" not in lowered
    assert "adopt zoning amendment" in lowered

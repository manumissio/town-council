def test_summarize_agenda_items_filters_notice_fragments_before_fallback_summary(monkeypatch):
    from pipeline.llm import LocalAI

    class _FakeLLM:
        def __call__(self, prompt, max_tokens=0, temperature=0.0):
            # Force deterministic fallback summary path.
            return {"choices": [{"text": "Too short"}]}

        def reset(self):
            return None

    ai = LocalAI()
    monkeypatch.setattr(ai, "_load_model", lambda: setattr(ai, "llm", _FakeLLM()))

    summary = ai.summarize_agenda_items(
        meeting_title="Cupertino Planning Commission",
        meeting_date="2021-11-22",
        items=[
            "Approve the Tentative Map (TM-2020-001).",
            "described in the notice or agenda for this meeting",
            "request card located in front of the Commission",
        ],
    )

    lowered = (summary or "").lower()
    assert "bluf: agenda includes 1 substantive item." in lowered
    assert "approve the tentative map" in lowered
    assert "described in the notice" not in lowered
    assert "request card located in front" not in lowered

def test_summarize_agenda_items_filters_notice_fragments_before_fallback_summary(monkeypatch):
    from pipeline.llm import LocalAI

    class _FakeProvider:
        def summarize_agenda_items(self, prompt, *, temperature, max_tokens):
            # Force deterministic fallback summary path.
            return "Too short"

    ai = LocalAI()
    monkeypatch.setattr(ai, "_get_provider", lambda: _FakeProvider())

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
    assert lowered.startswith("bluf:")
    assert "why this matters:" in lowered
    assert "top actions:" in lowered
    assert "unknowns:" in lowered
    assert "approve the tentative map" in lowered
    assert "described in the notice" not in lowered
    assert "request card located in front" not in lowered

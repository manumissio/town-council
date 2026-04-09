def test_deterministic_summary_discloses_partial_coverage_when_truncated(monkeypatch):
    from pipeline.llm import LocalAI

    class _FakeProvider:
        def summarize_agenda_items(self, prompt, *, temperature, max_tokens):
            return "BLUF: Too short"

    ai = LocalAI()
    monkeypatch.setattr(ai, "_get_provider", lambda: _FakeProvider())
    summary = ai.summarize_agenda_items(
        meeting_title="Council",
        meeting_date="2026-02-10",
        items=[{"title": "Approve contract", "description": "", "page_number": 1}],
        truncation_meta={"items_total": 10, "items_included": 3, "items_truncated": 7, "input_chars": 999},
    )
    lowered = (summary or "").lower()
    assert "first 3 of 10 agenda items" in lowered

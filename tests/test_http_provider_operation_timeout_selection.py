from pipeline.llm_provider import HttpInferenceProvider


def test_operation_timeout_selection_prefers_split_budgets(monkeypatch):
    provider = HttpInferenceProvider()
    monkeypatch.setattr(provider, "timeout_segment_seconds", 301)
    monkeypatch.setattr(provider, "timeout_summary_seconds", 181)
    monkeypatch.setattr(provider, "timeout_topics_seconds", 91)
    monkeypatch.setattr(provider, "timeout_seconds", 61)

    assert provider._timeout_for_operation("extract_agenda") == 301
    assert provider._timeout_for_operation("generate_json") == 301
    assert provider._timeout_for_operation("summarize_agenda_items") == 181
    assert provider._timeout_for_operation("summarize_text") == 181
    assert provider._timeout_for_operation("generate_topics") == 91
    assert provider._timeout_for_operation("unknown_op") == 61

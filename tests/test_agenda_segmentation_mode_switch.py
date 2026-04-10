def test_segmentation_mode_switch_changes_llm_acceptance(monkeypatch):
    import pipeline.llm as llm_mod
    from pipeline.llm import LocalAI

    def _fake_extract(_self, prompt, *, temperature, max_tokens):
        _ = (prompt, temperature, max_tokens)
        return " Committee Update (Page 2) - Brief note"

    LocalAI._instance = None
    monkeypatch.setattr(llm_mod, "LOCAL_AI_BACKEND", "http")
    monkeypatch.setattr(llm_mod.HttpInferenceProvider, "extract_agenda", _fake_extract)
    ai = LocalAI()

    monkeypatch.setattr(llm_mod, "AGENDA_SEGMENTATION_MODE", "aggressive")
    aggressive_items = ai.extract_agenda("[PAGE 2]\nX")

    monkeypatch.setattr(llm_mod, "AGENDA_SEGMENTATION_MODE", "recall")
    recall_items = ai.extract_agenda("[PAGE 2]\nX")

    assert len(aggressive_items) == 0
    assert len(recall_items) == 1
    assert "committee update" in recall_items[0]["title"].lower()

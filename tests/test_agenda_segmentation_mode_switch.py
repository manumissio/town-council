def test_segmentation_mode_switch_changes_llm_acceptance(monkeypatch):
    import pipeline.llm as llm_mod
    from pipeline.llm import LocalAI

    class _FakeLLM:
        def __call__(self, prompt, max_tokens=0, temperature=0.0):
            return {"choices": [{"text": " Committee Update (Page 2) - Brief note"}]}

        def reset(self):
            return None

    ai = LocalAI()
    monkeypatch.setattr(ai, "_load_model", lambda: setattr(ai, "llm", _FakeLLM()))

    monkeypatch.setattr(llm_mod, "AGENDA_SEGMENTATION_MODE", "aggressive")
    aggressive_items = ai.extract_agenda("[PAGE 2]\nX")

    monkeypatch.setattr(llm_mod, "AGENDA_SEGMENTATION_MODE", "recall")
    recall_items = ai.extract_agenda("[PAGE 2]\nX")

    assert len(aggressive_items) == 0
    assert len(recall_items) == 1
    assert "committee update" in recall_items[0]["title"].lower()

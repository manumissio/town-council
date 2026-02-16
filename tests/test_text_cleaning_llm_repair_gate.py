def test_llm_repair_gate_only_runs_for_implausible_lines(monkeypatch):
    from pipeline import text_cleaning

    monkeypatch.setattr(text_cleaning, "TEXT_REPAIR_ENABLE_LLM_ESCALATION", True)
    monkeypatch.setattr(text_cleaning, "TEXT_REPAIR_LLM_MAX_LINES_PER_DOC", 2)
    monkeypatch.setattr(text_cleaning, "TEXT_REPAIR_MIN_IMPLAUSIBILITY_SCORE", 0.2)
    monkeypatch.setattr(text_cleaning, "_repair_chunked_allcaps_line", lambda line: line)

    calls = {"n": 0}

    def fake_repair(line):
        calls["n"] += 1
        return line.replace(" ", "")

    text = "NORMAL SENTENCE WITH ADEQUATE SPACING\nPROCL AM AT ION C AL LINGAS"
    text_cleaning.postprocess_extracted_text(text, llm_repair_fn=fake_repair)
    assert calls["n"] == 1


def test_llm_repair_gate_respects_per_doc_budget(monkeypatch):
    from pipeline import text_cleaning

    monkeypatch.setattr(text_cleaning, "TEXT_REPAIR_ENABLE_LLM_ESCALATION", True)
    monkeypatch.setattr(text_cleaning, "TEXT_REPAIR_LLM_MAX_LINES_PER_DOC", 1)
    monkeypatch.setattr(text_cleaning, "TEXT_REPAIR_MIN_IMPLAUSIBILITY_SCORE", 0.2)
    monkeypatch.setattr(text_cleaning, "_repair_chunked_allcaps_line", lambda line: line)

    calls = {"n": 0}

    def fake_repair(line):
        calls["n"] += 1
        return line.replace(" ", "")

    text = "PROCL AM AT ION C AL LINGAS\nANN OT AT ED A G E N D A"
    text_cleaning.postprocess_extracted_text(text, llm_repair_fn=fake_repair)
    assert calls["n"] == 1

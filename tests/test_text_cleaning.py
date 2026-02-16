def test_postprocess_extracted_text_collapses_spaced_allcaps_preserving_word_boundaries():
    from pipeline.text_cleaning import postprocess_extracted_text

    raw = "C I T Y  C O U N C I L\nP R O C L A M A T I O N"
    out = postprocess_extracted_text(raw)

    assert "CITY COUNCIL" in out
    assert "PROCLAMATION" in out
    assert "CITYCOUNCIL" not in out


def test_postprocess_extracted_text_collapses_chunked_allcaps_words_conservatively():
    from pipeline.text_cleaning import postprocess_extracted_text

    raw = "\n".join(
        [
            "ANN OT AT ED A G E N D A",
            "PROCL AM AT ION",
            # Long mixed header-like runs should not collapse into merged gibberish tokens.
            "PROCL AM AT ION C AL LINGAS PE C I AL MEE TI NG OFT HE",
            "CITY OF CA",
        ]
    )
    out = postprocess_extracted_text(raw)

    assert "ANNOTATED AGENDA" in out
    assert "PROCLAMATION" in out
    assert "PROCLAMATIONCAL" not in out
    # Negative control: do not merge normal phrases.
    assert "CITY OF CA" in out


def test_postprocess_extracted_text_rejects_llm_non_spacing_edits(monkeypatch):
    from pipeline import text_cleaning

    monkeypatch.setattr(text_cleaning, "TEXT_REPAIR_ENABLE_LLM_ESCALATION", True)
    monkeypatch.setattr(text_cleaning, "TEXT_REPAIR_LLM_MAX_LINES_PER_DOC", 5)
    monkeypatch.setattr(text_cleaning, "TEXT_REPAIR_MIN_IMPLAUSIBILITY_SCORE", 0.3)
    raw = "PROCL AM AT ION C AL LINGAS PE C I AL"

    baseline = text_cleaning.postprocess_extracted_text(raw, llm_repair_fn=lambda _line: None)
    # Candidate rewrites words ("SPECIAL"), so validator should reject it and keep deterministic output.
    out = text_cleaning.postprocess_extracted_text(raw, llm_repair_fn=lambda _line: "PROCLAMATION CALLING A SPECIAL")
    assert out == baseline


def test_postprocess_extracted_text_accepts_llm_spacing_only_repair(monkeypatch):
    from pipeline import text_cleaning

    monkeypatch.setattr(text_cleaning, "TEXT_REPAIR_ENABLE_LLM_ESCALATION", True)
    monkeypatch.setattr(text_cleaning, "TEXT_REPAIR_LLM_MAX_LINES_PER_DOC", 5)
    monkeypatch.setattr(text_cleaning, "TEXT_REPAIR_MIN_IMPLAUSIBILITY_SCORE", 0.3)
    raw = "P R O C L A M A T I O N"
    out = text_cleaning.postprocess_extracted_text(raw, llm_repair_fn=lambda _line: "PROCLAMATION")
    assert "PROCLAMATION" in out

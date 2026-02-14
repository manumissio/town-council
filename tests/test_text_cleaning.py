def test_postprocess_extracted_text_collapses_spaced_allcaps_preserving_word_boundaries():
    from pipeline.text_cleaning import postprocess_extracted_text

    raw = "C I T Y  C O U N C I L\nP R O C L A M A T I O N"
    out = postprocess_extracted_text(raw)

    assert "CITY COUNCIL" in out
    assert "PROCLAMATION" in out
    assert "CITYCOUNCIL" not in out


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

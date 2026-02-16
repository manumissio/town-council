def test_agenda_segmentation_ignores_chunked_header_noise_and_keeps_real_items():
    from pipeline.llm import LocalAI
    from pipeline.text_cleaning import postprocess_extracted_text

    raw = """
    [PAGE 1]
    PROCL AM AT ION C AL LINGAS PE C I AL MEE TI NG OFT HE BERKE LE YCITY COUN CI L
    PUBLIC ADVISORY: THIS MEETING WILL BE CONDUCTED EXCLUSIVELY THROUGH VIDEOCONFERENCE
    [PAGE 2]
    1. Corridors Zoning Update
    Vote: All Ayes.
    2. San Pablo Avenue Specific Plan
    Vote: All Ayes.
    """

    cleaned = postprocess_extracted_text(raw)
    items = LocalAI().extract_agenda(cleaned)
    titles = [i.get("title", "") for i in items]
    lowered = " ".join(titles).lower()

    assert any("corridors zoning update" in t.lower() for t in titles)
    assert any("san pablo avenue specific plan" in t.lower() for t in titles)
    assert "proclamation" not in lowered
    assert "public advisory" not in lowered

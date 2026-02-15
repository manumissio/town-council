def test_strip_llm_acknowledgements_drops_preamble_lines():
    from pipeline.llm import _strip_llm_acknowledgements

    raw = "Okay, I understand.\nI will focus on the agenda.\nBLUF: Agenda covers 3 items.\nMore text."
    out = _strip_llm_acknowledgements(raw)
    assert out.startswith("BLUF:")


def test_strip_llm_acknowledgements_handles_inline_acknowledgement():
    from pipeline.llm import _strip_llm_acknowledgements

    raw = "Sure! BLUF: Agenda covers 2 items."
    out = _strip_llm_acknowledgements(raw)
    assert out.startswith("BLUF:")

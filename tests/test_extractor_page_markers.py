from pipeline.extractor import inject_page_markers


def test_inject_page_markers_formfeed_labels_first_chunk_as_page_1():
    pages = ["<p>page1</p>", "<p>page2</p>"]
    out = inject_page_markers(pages, mode="formfeed")
    assert "[PAGE 1]" in out
    assert "[PAGE 2]" in out
    assert out.index("[PAGE 1]") < out.index("page1")
    assert out.index("[PAGE 2]") < out.index("page2")


def test_inject_page_markers_div_page_treats_first_chunk_as_preamble():
    pages = ["<p>preamble</p>", "<p>p1</p>", "<p>p2</p>"]
    out = inject_page_markers(pages, mode="div_page")
    assert out.startswith("preamble")
    assert "[PAGE 1]" in out
    assert "[PAGE 2]" in out
    # Page 1 should be based on pages[1] (not pages[0]).
    assert out.index("[PAGE 1]") < out.index("p1")

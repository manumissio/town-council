from pipeline.indexer import _truncate_content_for_index


def test_truncate_content_for_index_marks_truncated_content():
    content = "x" * 60000
    indexed, truncated, original_chars, indexed_chars = _truncate_content_for_index(content)

    assert truncated is True
    assert original_chars == 60000
    assert indexed_chars == len(indexed)
    assert indexed_chars < original_chars


def test_truncate_content_for_index_handles_short_and_empty():
    indexed, truncated, original_chars, indexed_chars = _truncate_content_for_index("hello")
    assert indexed == "hello"
    assert truncated is False
    assert original_chars == 5
    assert indexed_chars == 5

    indexed, truncated, original_chars, indexed_chars = _truncate_content_for_index(None)
    assert indexed is None
    assert truncated is False
    assert original_chars == 0
    assert indexed_chars == 0

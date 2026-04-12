from pipeline import semantic_text
from pipeline.content_hash import compute_content_hash


def test_safe_text_collapses_whitespace_and_handles_empty_values():
    assert semantic_text._safe_text(None) == ""
    assert semantic_text._safe_text("  Housing\n\tupdate   memo  ") == "Housing update memo"


def test_catalog_semantic_text_truncates_to_configured_limit(monkeypatch):
    monkeypatch.setattr(semantic_text, "SEMANTIC_CONTENT_MAX_CHARS", 12)

    assert semantic_text.catalog_semantic_text("Budget hearing packet") == "Budget heari"


def test_catalog_semantic_source_hash_returns_none_for_short_payloads():
    assert semantic_text.catalog_semantic_source_hash(" \n\t ") is None
    assert semantic_text.catalog_semantic_source_hash("short text") is None


def test_catalog_semantic_source_hash_uses_normalized_semantic_payload(monkeypatch):
    monkeypatch.setattr(semantic_text, "SEMANTIC_CONTENT_MAX_CHARS", 40)
    expected_payload = "Budget hearing update with staff report"

    assert semantic_text.catalog_semantic_source_hash(
        " Budget\n hearing\t update   with staff report "
    ) == compute_content_hash(expected_payload)


def test_build_chunks_from_content_preserves_word_boundaries_and_chunk_limit():
    content = " ".join(f"word{index}" for index in range(40))

    chunks = semantic_text._build_chunks_from_content(content, max_chars=30)

    assert 1 < len(chunks) <= semantic_text.MAX_FALLBACK_CONTENT_CHUNKS
    assert all(len(chunk) <= 30 for chunk in chunks)
    assert chunks[0].startswith("word0 word1")
    assert chunks[-1]

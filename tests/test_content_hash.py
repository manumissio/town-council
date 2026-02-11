from pipeline.content_hash import compute_content_hash, normalize_text_for_hash


def test_normalize_text_for_hash_collapses_whitespace():
    assert normalize_text_for_hash("  a\n\nb\tc  ") == "a b c"


def test_compute_content_hash_ignores_whitespace_only_changes():
    h1 = compute_content_hash("A  B\nC")
    h2 = compute_content_hash("A B C")
    assert h1 == h2


def test_compute_content_hash_none_for_empty_or_whitespace():
    assert compute_content_hash(None) is None
    assert compute_content_hash("") is None
    assert compute_content_hash("   \n\t") is None


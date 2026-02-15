from pathlib import Path


def test_result_card_fetches_canonical_catalog_content_on_expand():
    """
    Regression: Full Text should be fetched from the DB (/catalog/{id}/content),
    not treated as equivalent to the Meilisearch content snippet.
    """
    source = Path("frontend/components/ResultCard.js").read_text(encoding="utf-8")

    assert "fetchCanonicalContent" in source
    assert "buildApiUrl(`/catalog/${hit.catalog_id}/content`)" in source


def test_result_card_uses_db_text_even_when_empty():
    """
    Empty DB content means 'not extracted yet' (common after startup purge).
    The UI should still treat that as canonical, rather than falling back to a stale snippet.
    """
    source = Path("frontend/components/ResultCard.js").read_text(encoding="utf-8")
    assert "if (typeof extractedTextOverride === \"string\") return extractedTextOverride;" in source


def test_result_card_shows_empty_state_for_empty_canonical_text_and_gates_snippet_fallback():
    """
    Regression: when canonical DB content is an empty string, do not fall through and show
    Meilisearch snippets. Only show snippets when the canonical fetch failed.
    """
    source = Path("frontend/components/ResultCard.js").read_text(encoding="utf-8")
    assert "typeof extractedTextOverride === \"string\"" in source
    assert "extractedTextOverride.trim() === \"\"" in source
    assert ") : canonicalTextFetchFailed ? (" in source

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


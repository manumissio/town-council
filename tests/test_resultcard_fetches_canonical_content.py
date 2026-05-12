from pathlib import Path


def test_result_card_fetches_canonical_catalog_content_on_expand():
    """
    Regression: Full Text should be fetched through the same-origin proxy so the
    browser never calls the protected FastAPI endpoint without API auth.
    """
    source = Path("frontend/components/ResultCard.js").read_text(encoding="utf-8")

    assert "fetchCanonicalContent" in source
    assert "buildProtectedCatalogApiUrl(`/catalog/${hit.catalog_id}/content`)" in source
    assert "buildApiUrl(`/catalog/${hit.catalog_id}/content`)" not in source


def test_result_card_fetches_derived_status_through_proxy():
    source = Path("frontend/components/ResultCard.js").read_text(encoding="utf-8")

    assert "fetchDerivedStatus" in source
    assert "buildProtectedCatalogApiUrl(`/catalog/${hit.catalog_id}/derived_status`)" in source
    assert "buildApiUrl(`/catalog/${hit.catalog_id}/derived_status`)" not in source


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


def test_result_card_fetches_canonical_agenda_items_for_live_mode():
    source = Path("frontend/components/ResultCard.js").read_text(encoding="utf-8")

    assert "fetchAgendaItems" in source
    assert "buildProtectedCatalogApiUrl(`/catalog/${hit.catalog_id}/agenda_items`)" in source
    assert "viewMode !== \"agenda\"" in source
    assert "demoMode || agendaItems !== null" in source

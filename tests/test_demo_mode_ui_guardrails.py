from pathlib import Path


def test_result_card_uses_demo_mode_mutation_guard():
    source = Path("frontend/components/ResultCard.js").read_text(encoding="utf-8")
    api_lib = Path("frontend/lib/api.js").read_text(encoding="utf-8")
    assert "const canMutate = !demoMode" in source
    assert "if (!hit.catalog_id || demoMode) return;" in source
    assert 'fetch(buildProtectedCatalogApiUrl(`/catalog/${hit.catalog_id}/derived_status`)' in source
    assert 'fetch(buildProtectedCatalogApiUrl(`/catalog/${hit.catalog_id}/content`)' in source
    assert "if (DEMO_MODE) {" in api_lib
    assert "return `.${demoPath}`;" in api_lib
    assert "/demo/catalog_${catalogStatusMatch[1]}_derived_status.json" in api_lib
    assert "/demo/catalog_${catalogContentMatch[1]}_content.json" in api_lib


def test_home_page_enables_demo_mode_banner_and_static_routing():
    source = Path("frontend/app/page.js").read_text(encoding="utf-8")
    assert "Demo Mode (Static)" in source
    assert 'fetch(buildApiUrl("/search"))' in source
    assert 'fetch(buildApiUrl("/metadata")' in source

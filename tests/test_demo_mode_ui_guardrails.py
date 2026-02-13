from pathlib import Path


def test_result_card_uses_demo_mode_mutation_guard():
    source = Path("frontend/components/ResultCard.js").read_text(encoding="utf-8")
    assert "const canMutate = !demoMode" in source
    assert "if (!hit.catalog_id || demoMode) return;" in source


def test_home_page_enables_demo_mode_banner_and_static_routing():
    source = Path("frontend/app/page.js").read_text(encoding="utf-8")
    assert "Demo Mode (Static)" in source
    assert 'fetch(buildApiUrl("/search"))' in source
    assert 'fetch(buildApiUrl("/metadata")' in source

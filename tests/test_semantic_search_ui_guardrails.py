from pathlib import Path


def test_home_page_has_semantic_search_mode_toggle():
    source = Path("frontend/app/page.js").read_text(encoding="utf-8")
    assert 'searchMode' in source
    search_source = Path("frontend/state/use-record-search.js").read_text(encoding="utf-8")
    assert '/search/semantic' in search_source


def test_search_hub_disables_sort_in_semantic_mode():
    source = Path("frontend/components/SearchHub.js").read_text(encoding="utf-8")
    assert 'searchMode !== "semantic"' in source
    assert "Sort: Semantic" in source

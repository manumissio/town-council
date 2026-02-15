from pathlib import Path


def test_home_page_search_includes_sort_param():
    source = Path("frontend/app/page.js").read_text(encoding="utf-8")
    assert "&sort=${encodeURIComponent(sortMode)}" in source


def test_search_hub_renders_sort_pill():
    source = Path("frontend/components/SearchHub.js").read_text(encoding="utf-8")
    assert "Sort: Newest" in source
    assert "cycleSortMode" in source


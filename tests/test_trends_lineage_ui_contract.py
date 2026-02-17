from pathlib import Path


def test_page_temporarily_hides_trends_panel_for_clarity():
    source = Path("frontend/app/page.js").read_text(encoding="utf-8")
    assert "We are pausing Topic Momentum/Civic Signals" in source
    assert "<TrendsPanel" not in source


def test_result_card_wires_lineage_timeline():
    source = Path("frontend/components/ResultCard.js").read_text(encoding="utf-8")
    assert "LineageTimeline" in source
    assert "catalogId={hit.catalog_id}" in source

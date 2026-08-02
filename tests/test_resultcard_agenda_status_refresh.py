from pathlib import Path


def test_result_card_surfaces_agenda_item_load_errors():
    source = Path("frontend/components/ResultCard.js").read_text(encoding="utf-8")

    assert "agendaLoadError" in source
    assert "Load agenda items" in source
    assert "Failed to load agenda items." in source


def test_result_card_surfaces_topic_action_errors_without_existing_topics():
    source = Path("frontend/components/ResultCard.js").read_text(encoding="utf-8")

    assert "(topics && topics.length > 0) || effectiveTopicsBlockReason || topicsActionError || topicsNotGeneratedYet" in source
    assert "{topicsActionError}" in source

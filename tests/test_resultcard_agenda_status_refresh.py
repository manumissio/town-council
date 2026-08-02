from pathlib import Path


def test_result_card_refreshes_derived_status_after_segmentation():
    """
    Regression: after agenda segmentation completes, the UI should refresh derived status so
    the "Not generated yet" badge clears without requiring a manual page refresh.
    """
    source = Path("frontend/components/ResultCard.js").read_text(encoding="utf-8")

    # Minimal (string-based) contract: agenda handler calls fetchDerivedStatus after success.
    assert "const handleGenerateAgenda" in source
    assert "fetchDerivedStatus();" in source


def test_result_card_surfaces_agenda_item_load_errors():
    source = Path("frontend/components/ResultCard.js").read_text(encoding="utf-8")

    assert "agendaLoadError" in source
    assert "Load agenda items" in source
    assert "Failed to load agenda items." in source


def test_result_card_surfaces_topic_action_errors_without_existing_topics():
    source = Path("frontend/components/ResultCard.js").read_text(encoding="utf-8")

    assert "(topics && topics.length > 0) || effectiveTopicsBlockReason || topicsActionError || topicsNotGeneratedYet" in source
    assert "{topicsActionError}" in source


def test_result_card_keeps_task_agenda_source_after_segmentation():
    source = Path("frontend/components/ResultCard.js").read_text(encoding="utf-8")

    assert "const items = result.items || [];" in source
    assert "setAgendaItems(items);" in source
    assert "if (items.length === 0) agendaRefreshes.push(fetchAgendaItems(signal));" in source
    assert "if (data.items.length === 0) fetchAgendaItems();" in source


def test_result_card_stops_reextract_state_updates_after_poll_cancellation():
    source = Path("frontend/components/ResultCard.js").read_text(encoding="utf-8")

    assert "async (_result, signal)" in source
    assert "await fetchCanonicalContent(signal);" in source
    assert "if (signal.aborted) return;" in source
    assert "await fetchDerivedStatus(signal);" in source

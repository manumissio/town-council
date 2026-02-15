import sys
from unittest.mock import MagicMock

# Prevent importing llama-cpp during unit tests.
sys.modules["llama_cpp"] = MagicMock()

from pipeline import tasks
from pipeline.models import AgendaItem, Document


def test_generate_summary_task_agenda_requires_segmentation_and_calls_agenda_items_summarizer(mocker):
    mock_db = MagicMock()
    catalog = MagicMock()
    # Make the content pass the low-signal quality gate (>=80 chars and enough distinct tokens).
    catalog.content = (
        "City Council agenda includes housing policy updates, budget review, "
        "public safety briefing, and committee reports. Discussion and votes may occur."
    )
    catalog.summary = None
    catalog.content_hash = "h1"
    catalog.summary_source_hash = None
    mock_db.get.return_value = catalog

    doc_query = MagicMock()
    doc_query.filter_by.return_value.first.return_value = MagicMock(category="agenda")

    items_query = MagicMock()
    items_query.filter_by.return_value.order_by.return_value.all.return_value = [
        MagicMock(title="Item One"),
        MagicMock(title="Item Two"),
        MagicMock(title="Item Three"),
    ]

    def _query_side_effect(model):
        if model is Document:
            return doc_query
        if model is AgendaItem:
            return items_query
        return MagicMock()

    mock_db.query.side_effect = _query_side_effect

    mocker.patch.object(tasks, "SessionLocal", return_value=mock_db)
    mock_ai = MagicMock()
    mock_ai.summarize_agenda_items.return_value = "BLUF: Agenda focuses on core policy and operational items."
    mocker.patch.object(tasks, "LocalAI", return_value=mock_ai)

    result = tasks.generate_summary_task.run(1, force=True)
    assert result["status"] == "complete"
    summary = result["summary"]
    assert summary.startswith("BLUF:")
    mock_ai.summarize_agenda_items.assert_called_once()


def test_generate_summary_task_agenda_returns_not_generated_yet_when_no_items(mocker):
    mock_db = MagicMock()
    catalog = MagicMock()
    catalog.content = (
        "Agenda text exists but segmentation has not run yet, so we should block."
        " This content is long enough to pass the quality gate."
    )
    catalog.summary = None
    catalog.content_hash = "h1"
    catalog.summary_source_hash = None
    mock_db.get.return_value = catalog

    doc_query = MagicMock()
    doc_query.filter_by.return_value.first.return_value = MagicMock(category="agenda")

    items_query = MagicMock()
    items_query.filter_by.return_value.order_by.return_value.all.return_value = []

    def _query_side_effect(model):
        if model is Document:
            return doc_query
        if model is AgendaItem:
            return items_query
        return MagicMock()

    mock_db.query.side_effect = _query_side_effect

    mocker.patch.object(tasks, "SessionLocal", return_value=mock_db)
    mock_ai = MagicMock()
    mocker.patch.object(tasks, "LocalAI", return_value=mock_ai)

    result = tasks.generate_summary_task.run(1, force=True)
    assert result["status"] == "not_generated_yet"
    assert "segmentation" in (result.get("reason") or "").lower()

import sys
from unittest.mock import MagicMock

sys.modules["llama_cpp"] = MagicMock()

from pipeline import tasks
from pipeline.models import AgendaItem, Document


def test_generate_summary_task_applies_payload_budget_and_truncation_meta(mocker):
    mock_db = MagicMock()
    catalog = MagicMock()
    catalog.content = "Long enough agenda content to pass quality gates for this test case."
    catalog.summary = None
    catalog.content_hash = "h1"
    catalog.summary_source_hash = None
    mock_db.get.return_value = catalog

    doc_query = MagicMock()
    doc_query.filter_by.return_value.first.return_value = MagicMock(category="agenda")

    long_desc = "x" * 800
    items_query = MagicMock()
    items_query.filter_by.return_value.order_by.return_value.all.return_value = [
        MagicMock(title=f"Item {i}", description=long_desc, classification="Agenda Item", result="", page_number=i)
        for i in range(1, 25)
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
    mock_ai.summarize_agenda_items.return_value = "BLUF: Budget test summary."
    mocker.patch.object(tasks, "LocalAI", return_value=mock_ai)
    mocker.patch.object(tasks, "AGENDA_SUMMARY_MAX_INPUT_CHARS", 1200)
    mocker.patch.object(tasks, "AGENDA_SUMMARY_MIN_RESERVED_OUTPUT_CHARS", 200)

    result = tasks.generate_summary_task.run(1, force=True)
    assert result["status"] == "complete"
    kwargs = mock_ai.summarize_agenda_items.call_args.kwargs
    trunc = kwargs["truncation_meta"]
    assert trunc["items_included"] < trunc["items_total"]
    assert trunc["items_truncated"] > 0
    assert trunc["input_chars"] <= 1000

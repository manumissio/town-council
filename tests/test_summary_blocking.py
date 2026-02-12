import sys
from unittest.mock import MagicMock

sys.modules["llama_cpp"] = MagicMock()

from pipeline import tasks


def test_generate_summary_task_blocks_low_signal_input(mocker):
    """
    Guardrail: do not run the model or save summary when extracted text is low-signal.
    """
    mock_db = MagicMock()
    catalog = MagicMock()
    catalog.content = "Agenda"
    catalog.summary = None
    catalog.content_hash = "h1"
    catalog.summary_source_hash = None
    mock_db.get.return_value = catalog
    mock_doc_query = MagicMock()
    mock_doc_query.filter_by.return_value.first.return_value = MagicMock(category="agenda")
    mock_db.query.return_value = mock_doc_query

    mocker.patch.object(tasks, "SessionLocal", return_value=mock_db)
    mock_ai = MagicMock()
    mocker.patch.object(tasks, "LocalAI", return_value=mock_ai)

    result = tasks.generate_summary_task.run(1, force=True)
    assert result["status"] == "blocked_low_signal"
    assert "Not enough extracted text" in result["reason"]
    mock_ai.summarize.assert_not_called()
    mock_db.commit.assert_not_called()

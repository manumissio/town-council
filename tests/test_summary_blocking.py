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
    mock_doc_query.filter_by.return_value.first.return_value = MagicMock(category="minutes")
    mock_db.query.return_value = mock_doc_query

    mocker.patch.object(tasks, "SessionLocal", return_value=mock_db)
    mock_ai = MagicMock()
    mocker.patch.object(tasks, "LocalAI", return_value=mock_ai)

    result = tasks.generate_summary_task.run(1, force=True)
    assert result["status"] == "blocked_low_signal"
    assert "Not enough extracted text" in result["reason"]
    mock_ai.summarize.assert_not_called()
    mock_db.commit.assert_not_called()


def test_generate_summary_task_keeps_success_when_reindex_and_embed_dispatch_fail(mocker):
    mock_db = MagicMock()
    catalog = MagicMock()
    catalog.content = (
        "City council meeting discussed housing updates, budget amendments, public safety, "
        "transportation priorities, and committee recommendations in enough detail to summarize."
    )
    catalog.summary = None
    catalog.content_hash = None
    catalog.summary_source_hash = None
    catalog.agenda_items_hash = None
    mock_db.get.return_value = catalog

    mock_doc_query = MagicMock()
    mock_doc_query.filter_by.return_value.first.return_value = MagicMock(category="minutes")
    mock_db.query.return_value = mock_doc_query

    mocker.patch.object(tasks, "SessionLocal", return_value=mock_db)
    mock_ai = MagicMock()
    mock_ai.summarize.return_value = "BLUF: Council advanced budget and housing work."
    mocker.patch.object(tasks, "LocalAI", return_value=mock_ai)
    mocker.patch.object(tasks, "reindex_catalog", side_effect=RuntimeError("search unavailable"))
    mocker.patch.object(tasks.embed_catalog_task, "delay", side_effect=RuntimeError("broker unavailable"))

    result = tasks.generate_summary_task.run(1, force=True)

    assert result["status"] == "complete"
    assert result["summary"].startswith("BLUF:")
    assert result["reindexed"] == 0
    assert result["reindex_failed"] == 1
    assert result["embed_enqueued"] == 0
    assert result["embed_dispatch_failed"] == 1
    mock_db.commit.assert_called_once()

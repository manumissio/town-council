import sys
from unittest.mock import MagicMock

sys.modules["llama_cpp"] = MagicMock()

from pipeline import tasks


def test_generate_topics_task_blocks_low_signal_input(mocker):
    """
    Guardrail: skip TF-IDF topic generation when source text is too weak/noisy.
    """
    mock_db = MagicMock()
    catalog = MagicMock()
    catalog.content = "Agenda"
    catalog.topics = ["Old"]
    catalog.content_hash = "h1"
    catalog.topics_source_hash = "h1"
    mock_db.get.return_value = catalog

    mocker.patch.object(tasks, "SessionLocal", return_value=mock_db)
    result = tasks.generate_topics_task.run(1, force=True)

    assert result["status"] == "blocked_low_signal"
    assert result["topics"] == []
    assert "Not enough extracted text" in result["reason"]
    mock_db.commit.assert_not_called()

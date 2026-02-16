from unittest.mock import MagicMock

from pipeline import tasks


def test_extract_votes_task_runs_and_returns_counters(mocker):
    mock_db = MagicMock()
    catalog = MagicMock()
    catalog.id = 99
    catalog.content = "Meeting text with vote lines."
    mock_db.get.return_value = catalog

    doc = MagicMock()
    doc.category = "minutes"
    doc.event = MagicMock(name="City Council", record_date="2026-01-10")
    doc_query = MagicMock()
    doc_query.filter_by.return_value.first.return_value = doc

    item = MagicMock()
    item.order = 1
    agenda_query = MagicMock()
    agenda_query.filter_by.return_value.order_by.return_value.all.return_value = [item]

    def query_side_effect(model):
        if model is tasks.Document:
            return doc_query
        return agenda_query

    mock_db.query.side_effect = query_side_effect

    mocker.patch.object(tasks, "SessionLocal", return_value=mock_db)
    mocker.patch.object(tasks, "LocalAI", return_value=MagicMock())
    mocker.patch.object(tasks, "ENABLE_VOTE_EXTRACTION", True)
    mocker.patch.object(
        tasks,
        "run_vote_extraction_for_catalog",
        return_value={
            "processed_items": 4,
            "updated_items": 3,
            "skipped_items": 1,
            "failed_items": 0,
            "skip_reasons": {"low_confidence": 1},
        },
    )
    reindex_mock = mocker.patch.object(tasks, "reindex_catalog")

    result = tasks.extract_votes_task.run(99, force=False)

    assert result["status"] == "complete"
    assert result["processed_items"] == 4
    assert result["updated_items"] == 3
    mock_db.commit.assert_called_once()
    reindex_mock.assert_called_once_with(99)


def test_extract_votes_task_requires_segmented_items(mocker):
    mock_db = MagicMock()
    catalog = MagicMock()
    catalog.id = 88
    catalog.content = "Meeting text"
    mock_db.get.return_value = catalog

    doc = MagicMock()
    doc.category = "agenda"
    doc.event = MagicMock(name="Council", record_date="2026-01-10")
    doc_query = MagicMock()
    doc_query.filter_by.return_value.first.return_value = doc

    agenda_query = MagicMock()
    agenda_query.filter_by.return_value.order_by.return_value.all.return_value = []

    def query_side_effect(model):
        if model is tasks.Document:
            return doc_query
        return agenda_query

    mock_db.query.side_effect = query_side_effect

    mocker.patch.object(tasks, "SessionLocal", return_value=mock_db)
    mocker.patch.object(tasks, "LocalAI", return_value=MagicMock())
    mocker.patch.object(tasks, "ENABLE_VOTE_EXTRACTION", True)

    result = tasks.extract_votes_task.run(88, force=False)

    assert result["status"] == "not_generated_yet"
    assert "Run segmentation first" in result["reason"]

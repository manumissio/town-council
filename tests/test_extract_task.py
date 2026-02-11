from unittest.mock import MagicMock


def test_extract_text_task_returns_error_without_retry_for_missing_file(mocker):
    """
    Missing files are not transient; we should return an error without retrying.
    """
    import pipeline.tasks as tasks

    db = MagicMock()
    db.get.return_value = MagicMock(id=10)
    mocker.patch.object(tasks, "SessionLocal", return_value=db)
    mocker.patch("pipeline.tasks.reextract_catalog_content", return_value={"error": "File not found on disk"})
    mocker.patch("pipeline.tasks.reindex_catalog")

    result = tasks.extract_text_task.run(10, force=True, ocr_fallback=True)
    assert "error" in result
    assert "File not found" in result["error"]
    db.commit.assert_not_called()


def test_extract_text_task_updates_db_and_attempts_reindex(mocker):
    import pipeline.tasks as tasks

    db = MagicMock()
    db.get.return_value = MagicMock(id=10)
    mocker.patch.object(tasks, "SessionLocal", return_value=db)
    mocker.patch("pipeline.tasks.reextract_catalog_content", return_value={"status": "updated", "catalog_id": 10, "chars": 1234})
    reindex = mocker.patch("pipeline.tasks.reindex_catalog", return_value={"status": "ok"})

    result = tasks.extract_text_task.run(10, force=True, ocr_fallback=False)
    assert result["status"] == "updated"
    db.commit.assert_called_once()
    reindex.assert_called_once_with(10)


from unittest.mock import MagicMock


def test_extract_text_task_returns_error_without_retry_for_missing_file(mocker):
    """
    Missing files are not transient; we should return an error without retrying.
    """
    import pipeline.tasks as tasks

    db = MagicMock()
    catalog = MagicMock(id=10, extraction_attempt_count=0, extraction_status="pending")
    db.get.return_value = catalog
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
    catalog = MagicMock(id=10, extraction_attempt_count=0, extraction_status="pending")
    db.get.return_value = catalog
    mocker.patch.object(tasks, "SessionLocal", return_value=db)
    mocker.patch("pipeline.tasks.reextract_catalog_content", return_value={"status": "updated", "catalog_id": 10, "chars": 1234})
    reindex = mocker.patch("pipeline.tasks.reindex_catalog", return_value={"status": "ok"})

    result = tasks.extract_text_task.run(10, force=True, ocr_fallback=False)
    assert result["status"] == "updated"
    db.commit.assert_called_once()
    reindex.assert_called_once_with(10)


def test_extract_text_task_retries_for_transient_empty_text(mocker):
    import pipeline.tasks as tasks

    db = MagicMock()
    catalog = MagicMock(id=10, extraction_attempt_count=0, extraction_status="pending")
    db.get.return_value = catalog
    mocker.patch.object(tasks, "SessionLocal", return_value=db)
    mocker.patch(
        "pipeline.tasks.reextract_catalog_content",
        return_value={"error": "extraction returned empty text"},
    )
    retry = mocker.patch.object(tasks.extract_text_task, "retry", side_effect=RuntimeError("retry requested"))

    try:
        tasks.extract_text_task.run(10, force=True, ocr_fallback=False)
    except RuntimeError as exc:
        assert str(exc) == "retry requested"
    else:
        raise AssertionError("expected extract_text_task to retry on transient empty-text extraction")

    db.rollback.assert_called_once()
    retry.assert_called_once()
    retry_exception = retry.call_args.kwargs["exc"]
    assert isinstance(retry_exception, RuntimeError)
    assert str(retry_exception) == "extraction returned empty text"


def test_extract_text_task_returns_reindex_error_after_successful_commit(mocker):
    import pipeline.tasks as tasks

    db = MagicMock()
    catalog = MagicMock(id=10, extraction_attempt_count=0, extraction_status="pending")
    db.get.return_value = catalog
    mocker.patch.object(tasks, "SessionLocal", return_value=db)
    mocker.patch(
        "pipeline.tasks.reextract_catalog_content",
        return_value={"status": "updated", "catalog_id": 10, "chars": 1234},
    )
    mocker.patch("pipeline.tasks.reindex_catalog", side_effect=RuntimeError("search unavailable"))

    result = tasks.extract_text_task.run(10, force=True, ocr_fallback=False)

    assert result["status"] == "updated"
    assert result["reindex_error"] == "search unavailable"
    db.commit.assert_called_once()


def test_extract_text_task_force_bypasses_terminal_failure_state(mocker):
    import pipeline.tasks as tasks

    db = MagicMock()
    catalog = MagicMock(id=10, extraction_attempt_count=3, extraction_status="failed_terminal")
    db.get.return_value = catalog
    mocker.patch.object(tasks, "SessionLocal", return_value=db)
    extractor = mocker.patch(
        "pipeline.tasks.reextract_catalog_content",
        return_value={"status": "updated", "catalog_id": 10, "chars": 555},
    )
    mocker.patch("pipeline.tasks.reindex_catalog", return_value={"status": "ok"})

    result = tasks.extract_text_task.run(10, force=True, ocr_fallback=False)

    assert result["status"] == "updated"
    extractor.assert_called_once()
    assert extractor.call_args.kwargs["force"] is True

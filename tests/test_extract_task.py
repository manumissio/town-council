from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import sessionmaker

from pipeline import extractor, indexer, task_runtime, tasks
from pipeline.models import Catalog, Document, Event, Place


EXTRACTED_TEXT = "Council reviewed the budget amendment and adopted the revised allocation. " * 20


def _seed_catalog(db_session, catalog_path: str, *, catalog_id: int = 10) -> Catalog:
    place = Place(
        name=f"extract-place-{catalog_id}",
        state="CA",
        ocd_division_id=f"ocd-division/country:us/state:ca/place:extract-{catalog_id}",
    )
    event = Event(
        ocd_id=f"ocd-event/extract-{catalog_id}",
        place=place,
        name="City Council",
        record_date=date(2026, 1, 10),
    )
    catalog = Catalog(
        id=catalog_id,
        url_hash=f"extract-{catalog_id}",
        location=catalog_path,
        filename=f"extract-{catalog_id}.pdf",
        extraction_attempt_count=0,
        extraction_status="pending",
    )
    document = Document(
        place=place,
        event=event,
        catalog=catalog,
        category="minutes",
    )
    db_session.add_all([place, event, catalog, document])
    db_session.commit()
    return catalog


def _patch_task_session(mocker, shared_engine) -> None:
    task_db = sessionmaker(bind=shared_engine)()
    mocker.patch.object(task_runtime, "task_session", return_value=task_db)


def _patch_successful_tika(mocker) -> None:
    mocker.patch.object(extractor.parser, "from_file", return_value={"content": EXTRACTED_TEXT})


def _patch_meilisearch_client(mocker) -> MagicMock:
    search_client = MagicMock()
    search_client.index.return_value.delete_documents.return_value = SimpleNamespace(
        task_uid=17
    )
    search_client.wait_for_task.return_value = SimpleNamespace(
        status="succeeded",
        error=None,
    )
    mocker.patch.object(indexer.meilisearch, "Client", return_value=search_client)
    return search_client


def test_extract_text_task_returns_error_without_retry_for_missing_file(
    mocker,
    tmp_path,
    monkeypatch,
    db_session,
    shared_engine,
):
    missing_path = tmp_path / "missing.pdf"
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    _seed_catalog(db_session, str(missing_path))
    _patch_task_session(mocker, shared_engine)

    extraction_result = tasks.extract_text_task.run(10, force=True, ocr_fallback=True)

    assert extraction_result["error"] == "File not found on disk"
    persisted_catalog = db_session.get(Catalog, 10)
    db_session.refresh(persisted_catalog)
    assert persisted_catalog.extraction_status == "pending"


def test_extract_text_task_updates_db_and_attempts_reindex(
    mocker,
    tmp_path,
    monkeypatch,
    db_session,
    shared_engine,
):
    catalog_path = tmp_path / "minutes.pdf"
    catalog_path.write_bytes(b"test document")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    _seed_catalog(db_session, str(catalog_path))
    _patch_task_session(mocker, shared_engine)
    _patch_successful_tika(mocker)
    search_client = _patch_meilisearch_client(mocker)

    extraction_result = tasks.extract_text_task.run(10, force=True, ocr_fallback=False)

    assert extraction_result["status"] == "updated"
    persisted_catalog = db_session.get(Catalog, 10)
    db_session.refresh(persisted_catalog)
    assert "budget amendment" in persisted_catalog.content
    assert persisted_catalog.extraction_status == "complete"
    assert search_client.index.return_value.add_documents.called


def test_extract_text_task_retries_for_transient_empty_text(
    mocker,
    tmp_path,
    monkeypatch,
):
    catalog_path = tmp_path / "empty.pdf"
    catalog_path.write_bytes(b"test document")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    catalog = Catalog(
        id=10,
        url_hash="extract-empty",
        location=str(catalog_path),
        extraction_attempt_count=0,
        extraction_status="pending",
    )
    task_db = MagicMock()
    task_db.get.return_value = catalog
    mocker.patch.object(task_runtime, "task_session", return_value=task_db)
    mocker.patch.object(extractor.parser, "from_file", return_value={"content": ""})
    mocker.patch.object(extractor.time, "sleep")
    retry_error = RuntimeError("retry requested")
    retry = mocker.patch.object(tasks.extract_text_task, "retry", side_effect=retry_error)

    with pytest.raises(RuntimeError, match="retry requested"):
        tasks.extract_text_task.run(10, force=True, ocr_fallback=False)

    task_db.rollback.assert_called_once()
    task_db.close.assert_called_once()
    assert retry.call_args.kwargs["countdown"] == 60
    assert str(retry.call_args.kwargs["exc"]) == "Extraction returned empty text"


def test_extract_text_task_returns_reindex_error_after_successful_commit(
    mocker,
    tmp_path,
    monkeypatch,
    db_session,
    shared_engine,
):
    catalog_path = tmp_path / "reindex-failure.pdf"
    catalog_path.write_bytes(b"test document")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    _seed_catalog(db_session, str(catalog_path))
    _patch_task_session(mocker, shared_engine)
    _patch_successful_tika(mocker)
    mocker.patch.object(indexer.meilisearch, "Client", side_effect=ConnectionError("search unavailable"))

    extraction_result = tasks.extract_text_task.run(10, force=True, ocr_fallback=False)

    assert extraction_result["status"] == "updated"
    assert extraction_result["reindex_error"] == "search unavailable"
    persisted_catalog = db_session.get(Catalog, 10)
    db_session.refresh(persisted_catalog)
    assert persisted_catalog.extraction_status == "complete"


def test_extract_text_task_force_bypasses_terminal_failure_state(
    mocker,
    tmp_path,
    monkeypatch,
    db_session,
    shared_engine,
):
    catalog_path = tmp_path / "terminal.pdf"
    catalog_path.write_bytes(b"test document")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    catalog = _seed_catalog(db_session, str(catalog_path))
    catalog.content = "Old extracted content that should be replaced."
    catalog.extraction_attempt_count = 3
    catalog.extraction_status = "failed_terminal"
    db_session.commit()
    _patch_task_session(mocker, shared_engine)
    _patch_successful_tika(mocker)
    _patch_meilisearch_client(mocker)

    extraction_result = tasks.extract_text_task.run(10, force=True, ocr_fallback=False)

    assert extraction_result["status"] == "updated"
    persisted_catalog = db_session.get(Catalog, 10)
    db_session.refresh(persisted_catalog)
    assert persisted_catalog.extraction_status == "complete"
    assert "budget amendment" in persisted_catalog.content

from contextlib import contextmanager
import json
from pathlib import Path
import pytest
from unittest.mock import MagicMock
import sys

sys.modules["llama_cpp"] = MagicMock()
from pipeline import agenda_worker
from pipeline.agenda_worker import run_agenda_segmentation_backfill, segment_document_agenda
from pipeline import profiling
from pipeline.models import Place, Event, Document, Catalog, AgendaItem

def test_agenda_segmentation_logic(db_session, mocker):
    """
    Test: Does the agenda worker persist resolved agenda items?
    """
    # 1. Setup Data
    place = Place(name="Test City", state="CA", ocd_division_id="ocd-city")
    db_session.add(place)
    db_session.flush()

    event = Event(name="Test Meeting", place_id=place.id, ocd_division_id="ocd-city")
    db_session.add(event)
    db_session.flush()

    catalog = Catalog(
        filename="test.pdf",
        url_hash="test_hash_123",
        content="This is the raw text of an agenda. Item 1: Zoning. Item 2: Budget.",
        url="http://test.com/test.pdf"
    )
    db_session.add(catalog)
    db_session.flush()

    doc = Document(event_id=event.id, catalog_id=catalog.id, place_id=place.id)
    db_session.add(doc)
    db_session.commit()

    # 2. Mock resolver output (Legistar-first path)
    mocker.patch("pipeline.agenda_worker.LocalAI", return_value=MagicMock())
    reindex_spy = mocker.patch("pipeline.agenda_worker.reindex_catalog")
    mocker.patch("pipeline.agenda_worker.resolve_agenda_items", return_value={
        "items": [
            {"order": 1, "title": "Zoning Change", "description": "Discussion about Main St", "classification": "Action", "result": "Passed", "page_number": 4},
            {"order": 2, "title": "Budget 2026", "description": "Reviewing fiscal goals", "classification": "Discussion", "result": "", "page_number": 6},
        ],
        "source_used": "legistar",
        "quality_score": 81,
        "confidence": "high",
    })

    # 3. Action: Run the segmentation logic
    segment_document_agenda(catalog.id)

    # 4. Verify: Did it save to the database?
    items = db_session.query(AgendaItem).filter_by(catalog_id=catalog.id).order_by(AgendaItem.order).all()
    
    assert len(items) == 2
    assert items[0].title == "Zoning Change"
    assert items[0].classification == "Action"
    assert items[0].page_number == 4
    assert items[1].title == "Budget 2026"
    assert items[1].event_id == event.id
    reindex_spy.assert_called_once_with(catalog.id)


def test_segment_document_persists_failed_status_after_transaction_error(db_session, mocker):
    place = Place(name="Failure City", state="CA", ocd_division_id="ocd-failure-city")
    db_session.add(place)
    db_session.flush()
    event = Event(name="Failure Meeting", place_id=place.id, ocd_division_id=place.ocd_division_id)
    db_session.add(event)
    db_session.flush()
    catalog = Catalog(
        url_hash="agenda-transaction-error",
        content="Agenda Item 1: Housing Update",
        url="https://example.com/agenda-transaction-error",
    )
    db_session.add(catalog)
    db_session.flush()
    db_session.add(Document(event_id=event.id, catalog_id=catalog.id, place_id=place.id, category="agenda"))
    duplicate_ocd_id = "ocd-agenda-item/legacy-duplicate"
    db_session.add(
        AgendaItem(
            ocd_id=duplicate_ocd_id,
            catalog_id=catalog.id,
            event_id=event.id,
            title="Existing item",
        )
    )
    db_session.commit()

    def poison_agenda_transaction(session, _catalog, _document, _local_ai):
        session.add(
            AgendaItem(
                ocd_id=duplicate_ocd_id,
                catalog_id=catalog.id,
                event_id=event.id,
                title="Duplicate item",
            )
        )
        session.flush()
        raise AssertionError("duplicate agenda item must fail")

    @contextmanager
    def session_factory():
        yield db_session

    mocker.patch.object(agenda_worker, "db_session", session_factory)
    mocker.patch.object(agenda_worker, "resolve_agenda_items", side_effect=poison_agenda_transaction)
    mocker.patch.object(agenda_worker, "LocalAI", return_value=MagicMock())

    segment_document_agenda(catalog.id)

    db_session.expire_all()
    refreshed = db_session.get(Catalog, catalog.id)
    assert refreshed.agenda_segmentation_status == "failed"
    assert refreshed.agenda_segmentation_error


def test_segment_document_counts_only_persisted_items(db_session, mocker):
    place = Place(name="Mixed City", state="CA", ocd_division_id="ocd-mixed-city")
    db_session.add(place)
    db_session.flush()
    event = Event(name="Mixed Meeting", place_id=place.id, ocd_division_id=place.ocd_division_id)
    db_session.add(event)
    db_session.flush()
    catalog = Catalog(url_hash="agenda-mixed-titles", content="Agenda", url="https://example.com/mixed")
    db_session.add(catalog)
    db_session.flush()
    db_session.add(Document(event_id=event.id, catalog_id=catalog.id, place_id=place.id, category="agenda"))
    db_session.commit()
    mocker.patch.object(agenda_worker, "LocalAI", return_value=MagicMock())
    mocker.patch.object(agenda_worker, "reindex_catalog")
    mocker.patch.object(
        agenda_worker,
        "resolve_agenda_items",
        return_value={
            "items": [{"order": 1, "title": "  "}, {"order": 2, "title": "Kept Item"}],
            "source_used": "llm",
            "quality_score": 50,
        },
    )

    segment_document_agenda(catalog.id)

    db_session.expire_all()
    refreshed = db_session.get(Catalog, catalog.id)
    assert refreshed.agenda_segmentation_status == "complete"
    assert refreshed.agenda_segmentation_item_count == 1
    assert [row.title for row in db_session.query(AgendaItem).filter_by(catalog_id=catalog.id).all()] == ["Kept Item"]


def test_run_agenda_segmentation_backfill_uses_maintenance_metrics(mocker):
    mocker.patch(
        "pipeline.agenda_worker.select_catalog_ids_for_agenda_segmentation",
        side_effect=[[101, 102, 103]],
    )

    @contextmanager
    def _fake_db_session():
        yield MagicMock()

    @contextmanager
    def _fake_timeout(timeout_seconds):
        assert timeout_seconds == 17
        yield

    @contextmanager
    def _fake_capture():
        yield {"timeout": 2, "empty_response": 1}

    mocker.patch("pipeline.agenda_worker.db_session", _fake_db_session)
    mocker.patch("pipeline.agenda_worker.segment_timeout_override", _fake_timeout)
    mocker.patch("pipeline.agenda_worker.capture_agenda_fallback_events", _fake_capture)
    segment_spy = mocker.patch(
        "pipeline.agenda_worker.segment_catalog_with_mode",
        side_effect=[
            {"status": "complete", "llm_attempted": 1, "llm_skipped_heuristic_first": 0, "heuristic_complete": 0},
            {"status": "empty", "llm_attempted": 0, "llm_skipped_heuristic_first": 1, "heuristic_complete": 0},
            {"status": "complete", "llm_attempted": 0, "llm_skipped_heuristic_first": 1, "heuristic_complete": 1},
        ],
    )

    counts = run_agenda_segmentation_backfill(segment_mode="maintenance", agenda_timeout_seconds=17)

    assert counts["selected"] == 3
    assert counts["complete"] == 2
    assert counts["empty"] == 1
    assert counts["timeout_fallbacks"] == 2
    assert counts["empty_response_fallbacks"] == 1
    assert counts["llm_attempted"] == 1
    assert counts["llm_skipped_heuristic_first"] == 2
    assert counts["heuristic_complete"] == 1
    assert counts["llm_timeout_then_fallback"] == 2
    assert segment_spy.call_count == 3


def test_agenda_backfill_records_before_and_after_eligibility(monkeypatch, mocker, tmp_path: Path):
    monkeypatch.setenv(profiling.PROFILE_RUN_ID_ENV, "profile_run")
    monkeypatch.setenv(profiling.PROFILE_ARTIFACT_DIR_ENV, str(tmp_path))
    mocker.patch(
        "pipeline.agenda_worker.select_catalog_ids_for_agenda_segmentation",
        side_effect=[[31, 32], [32]],
    )

    @contextmanager
    def _fake_db_session():
        yield MagicMock()

    @contextmanager
    def _fake_timeout(_timeout_seconds):
        yield

    @contextmanager
    def _fake_capture():
        yield {"timeout": 0, "empty_response": 0}

    mocker.patch("pipeline.agenda_worker.db_session", _fake_db_session)
    mocker.patch("pipeline.agenda_worker.segment_timeout_override", _fake_timeout)
    mocker.patch("pipeline.agenda_worker.capture_agenda_fallback_events", _fake_capture)
    mocker.patch(
        "pipeline.agenda_worker.segment_catalog_with_mode",
        return_value={"status": "complete"},
    )

    counts = run_agenda_segmentation_backfill(segment_mode="maintenance")

    rows = [json.loads(line) for line in (tmp_path / "spans.jsonl").read_text(encoding="utf-8").splitlines()]
    eligibility_rows = [row for row in rows if row["event_type"] == "phase_eligibility"]
    assert [(row["boundary"], row["eligible_ids"]) for row in eligibility_rows] == [
        ("before", [31, 32]),
        ("after", [32]),
    ]
    assert counts["selected"] == 2


def test_agenda_backfill_records_paired_empty_eligibility(monkeypatch, mocker, tmp_path: Path):
    monkeypatch.setenv(profiling.PROFILE_RUN_ID_ENV, "profile_run")
    monkeypatch.setenv(profiling.PROFILE_ARTIFACT_DIR_ENV, str(tmp_path))
    mocker.patch(
        "pipeline.agenda_worker.select_catalog_ids_for_agenda_segmentation",
        side_effect=[[]],
    )

    @contextmanager
    def _fake_db_session():
        yield MagicMock()

    mocker.patch("pipeline.agenda_worker.db_session", _fake_db_session)

    counts = run_agenda_segmentation_backfill()

    rows = [json.loads(line) for line in (tmp_path / "spans.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [(row["boundary"], row["eligible_ids"]) for row in rows] == [
        ("before", []),
        ("after", []),
    ]
    assert counts["selected"] == 0


def test_agenda_backfill_omits_after_eligibility_when_work_fails(monkeypatch, mocker, tmp_path: Path):
    monkeypatch.setenv(profiling.PROFILE_RUN_ID_ENV, "profile_run")
    monkeypatch.setenv(profiling.PROFILE_ARTIFACT_DIR_ENV, str(tmp_path))
    mocker.patch(
        "pipeline.agenda_worker.select_catalog_ids_for_agenda_segmentation",
        side_effect=[[31]],
    )

    @contextmanager
    def _fake_db_session():
        yield MagicMock()

    @contextmanager
    def _fake_timeout(_timeout_seconds):
        yield

    @contextmanager
    def _fake_capture():
        yield {"timeout": 0, "empty_response": 0}

    mocker.patch("pipeline.agenda_worker.db_session", _fake_db_session)
    mocker.patch("pipeline.agenda_worker.segment_timeout_override", _fake_timeout)
    mocker.patch("pipeline.agenda_worker.capture_agenda_fallback_events", _fake_capture)
    mocker.patch(
        "pipeline.agenda_worker.segment_catalog_with_mode",
        side_effect=RuntimeError("agenda failed"),
    )

    with pytest.raises(RuntimeError, match="agenda failed"):
        run_agenda_segmentation_backfill(segment_mode="maintenance")

    rows = [json.loads(line) for line in (tmp_path / "spans.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [row["boundary"] for row in rows] == ["before"]


def test_agenda_backfill_propagates_after_selector_failure(monkeypatch, mocker, tmp_path: Path):
    monkeypatch.setenv(profiling.PROFILE_RUN_ID_ENV, "profile_run")
    monkeypatch.setenv(profiling.PROFILE_ARTIFACT_DIR_ENV, str(tmp_path))
    mocker.patch(
        "pipeline.agenda_worker.select_catalog_ids_for_agenda_segmentation",
        side_effect=[[31], RuntimeError("selector failed")],
    )

    @contextmanager
    def _fake_db_session():
        yield MagicMock()

    @contextmanager
    def _fake_timeout(_timeout_seconds):
        yield

    @contextmanager
    def _fake_capture():
        yield {"timeout": 0, "empty_response": 0}

    mocker.patch("pipeline.agenda_worker.db_session", _fake_db_session)
    mocker.patch("pipeline.agenda_worker.segment_timeout_override", _fake_timeout)
    mocker.patch("pipeline.agenda_worker.capture_agenda_fallback_events", _fake_capture)
    mocker.patch(
        "pipeline.agenda_worker.segment_catalog_with_mode",
        return_value={"status": "complete"},
    )

    with pytest.raises(RuntimeError, match="selector failed"):
        run_agenda_segmentation_backfill(segment_mode="maintenance")

    rows = [json.loads(line) for line in (tmp_path / "spans.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [row["boundary"] for row in rows] == ["before"]

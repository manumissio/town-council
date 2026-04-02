import pytest
from unittest.mock import MagicMock
import sys

# Mock heavy libraries
sys.modules["llama_cpp"] = MagicMock()
sys.modules["tika"] = MagicMock()

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from pipeline.run_pipeline import process_document_chunk
from pipeline.tasks import select_catalog_ids_for_summary_hydration, run_summary_hydration_backfill
from pipeline.agenda_worker import select_catalog_ids_for_agenda_segmentation
from pipeline.table_worker import select_catalog_ids_for_table_extraction
from pipeline.models import Base, Catalog, Document, AgendaItem, Event, Place
from pipeline.city_scope import ordered_hydration_cities, source_aliases_for_city


def test_document_chunk_worker(mocker):
    """
    Test: Does chunk worker orchestrate OCR and extraction metadata for one document?
    """
    # Mock DB
    mock_catalog = MagicMock()
    mock_catalog.id = 1
    mock_catalog.location = "/tmp/test.pdf"
    mock_catalog.content = None
    mock_catalog.entities = None
    
    mock_db = MagicMock()
    mock_db.get.return_value = mock_catalog
    
    # Mock DB Connection context
    mock_session = MagicMock()
    mock_session.return_value = mock_db
    mocker.patch("sqlalchemy.orm.sessionmaker", return_value=mock_session)
    mocker.patch("pipeline.models.db_connect")

    # Mock Extractor only. NLP enrichment now runs in the batch path.
    extract_text_spy = mocker.patch("pipeline.extractor.extract_text", return_value="Extracted Text")
    mock_db.execute.return_value = None

    # Action
    processed_count = process_document_chunk([1], ocr_fallback_enabled=False)

    # Verify
    assert processed_count == 1
    assert mock_catalog.content == "Extracted Text"
    assert mock_catalog.entities is None
    extract_text_spy.assert_called_once_with("/tmp/test.pdf", ocr_fallback_enabled=False)
    mock_db.commit.assert_called_once()
    mock_db.close.assert_called_once()


def test_run_entity_backfill_returns_zero_counts_when_nothing_is_selected(mocker):
    mock_session = MagicMock()
    mock_session.__enter__.return_value = mock_session
    mock_session.__exit__.return_value = False
    mocker.patch("pipeline.backfill_entities.db_session", return_value=mock_session)
    mocker.patch("pipeline.backfill_entities.select_catalog_ids_for_entity_backfill", return_value=[])

    from pipeline.backfill_entities import run_entity_backfill

    assert run_entity_backfill() == {"selected": 0, "complete": 0}


@pytest.fixture
def batching_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    place = Place(
        name="sample",
        state="CA",
        ocd_division_id="ocd-division/country:us/state:ca/place:sample",
        crawler_name="sample",
    )
    db.add(place)
    db.flush()

    event = Event(place_id=place.id, ocd_division_id=place.ocd_division_id, name="Sample Council")
    db.add(event)
    db.flush()

    yield db, event, place

    db.close()


def _add_catalog(db, event, place, *, category, content="content", summary=None, segmentation_status=None):
    catalog = Catalog(
        url_hash=f"{category}-{summary}-{segmentation_status}-{content}-{db.query(Catalog).count()}",
        location="/tmp/doc.pdf",
        content=content,
        summary=summary,
        agenda_segmentation_status=segmentation_status,
    )
    db.add(catalog)
    db.flush()
    db.add(
        Document(
            place_id=place.id,
            event_id=event.id,
            catalog_id=catalog.id,
            category=category,
            url=f"https://example.com/{catalog.id}",
        )
    )
    db.flush()
    return catalog


def test_select_catalog_ids_for_summary_hydration_filters_agenda_without_items(batching_db):
    db, event, place = batching_db
    minutes_catalog = _add_catalog(db, event, place, category="minutes", content="minutes text", summary=None)
    agenda_with_items = _add_catalog(
        db,
        event,
        place,
        category="agenda",
        content="agenda text",
        summary=None,
        segmentation_status="complete",
    )
    agenda_without_items = _add_catalog(
        db,
        event,
        place,
        category="agenda",
        content="agenda text",
        summary=None,
        segmentation_status=None,
    )
    summarized_catalog = _add_catalog(db, event, place, category="minutes", content="done", summary="already done")
    db.add(AgendaItem(catalog_id=agenda_with_items.id, event_id=event.id, order=1, title="Item 1"))
    db.commit()

    selected = select_catalog_ids_for_summary_hydration(db)

    assert minutes_catalog.id in selected
    assert agenda_with_items.id in selected
    assert agenda_without_items.id not in selected
    assert summarized_catalog.id not in selected


def test_select_catalog_ids_for_summary_hydration_treats_agenda_html_like_agenda(batching_db):
    db, event, place = batching_db
    agenda_html_with_items = _add_catalog(
        db,
        event,
        place,
        category="agenda_html",
        content="agenda html text",
        summary=None,
        segmentation_status="complete",
    )
    agenda_html_without_items = _add_catalog(
        db,
        event,
        place,
        category="agenda_html",
        content="agenda html text",
        summary=None,
        segmentation_status=None,
    )
    db.add(AgendaItem(catalog_id=agenda_html_with_items.id, event_id=event.id, order=1, title="Item 1"))
    db.commit()

    selected = select_catalog_ids_for_summary_hydration(db)

    assert agenda_html_with_items.id in selected
    assert agenda_html_without_items.id not in selected


def test_select_catalog_ids_for_agenda_segmentation_excludes_empty_terminal_state(batching_db):
    db, event, place = batching_db
    pending_catalog = _add_catalog(db, event, place, category="agenda", content="agenda text", segmentation_status=None)
    failed_catalog = _add_catalog(db, event, place, category="agenda", content="agenda text", segmentation_status="failed")
    empty_catalog = _add_catalog(db, event, place, category="agenda", content="agenda text", segmentation_status="empty")
    complete_catalog = _add_catalog(db, event, place, category="agenda", content="agenda text", segmentation_status="complete")
    db.add(AgendaItem(catalog_id=complete_catalog.id, event_id=event.id, order=1, title="Item 1", page_number=None))
    db.commit()

    selected = select_catalog_ids_for_agenda_segmentation(db)

    assert pending_catalog.id in selected
    assert failed_catalog.id in selected
    assert complete_catalog.id in selected
    assert empty_catalog.id not in selected


def test_run_summary_hydration_backfill_counts_outcomes(mocker):
    mock_db = MagicMock()
    mock_db.close.return_value = None
    mocker.patch("pipeline.tasks.SessionLocal", return_value=mock_db)
    mocker.patch("pipeline.tasks.select_catalog_ids_for_summary_hydration", return_value=[1, 2, 3])
    summarize_spy = mocker.patch(
        "pipeline.tasks.summarize_catalog_with_maintenance_mode",
        side_effect=[
            {"status": "complete", "completion_mode": "agenda_deterministic"},
            {"status": "blocked_low_signal"},
            {"status": "complete", "completion_mode": "llm"},
        ],
    )

    counts = run_summary_hydration_backfill()

    assert counts["selected"] == 3
    assert counts["complete"] == 2
    assert counts["blocked_low_signal"] == 1
    assert counts["agenda_deterministic_complete"] == 1
    assert counts["llm_complete"] == 1
    assert counts["deterministic_fallback_complete"] == 0
    assert summarize_spy.call_count == 3


def test_select_catalog_ids_for_summary_hydration_can_filter_by_city(batching_db):
    db, event, place = batching_db
    event.source = "san mateo"
    san_mateo_catalog = _add_catalog(db, event, place, category="minutes", content="minutes text", summary=None)

    other_place = Place(
        name="hayward",
        state="CA",
        ocd_division_id="ocd-division/country:us/state:ca/place:hayward",
        crawler_name="hayward",
    )
    db.add(other_place)
    db.flush()
    other_event = Event(
        place_id=other_place.id,
        ocd_division_id=other_place.ocd_division_id,
        name="Hayward Council",
        source="hayward",
    )
    db.add(other_event)
    db.flush()
    hayward_catalog = _add_catalog(db, other_event, other_place, category="minutes", content="minutes text", summary=None)
    db.commit()

    selected = select_catalog_ids_for_summary_hydration(db, city="san_mateo")

    assert san_mateo_catalog.id in selected
    assert hayward_catalog.id not in selected


def test_city_scope_helpers_return_expected_defaults():
    assert source_aliases_for_city("san_mateo") == {"san_mateo", "san mateo"}
    assert ordered_hydration_cities() == ["hayward", "sunnyvale", "berkeley", "cupertino", "san_mateo"]


def test_select_catalog_ids_for_table_extraction_only_returns_pending_real_files(batching_db):
    db, event, place = batching_db
    pending_catalog = _add_catalog(db, event, place, category="minutes", content="minutes text")
    done_catalog = _add_catalog(db, event, place, category="minutes", content="done")
    done_catalog.tables = [["row"]]
    placeholder_catalog = _add_catalog(db, event, place, category="minutes", content="placeholder")
    placeholder_catalog.location = "placeholder"
    db.commit()

    selected = select_catalog_ids_for_table_extraction(db)

    assert pending_catalog.id in selected
    assert done_catalog.id not in selected
    assert placeholder_catalog.id not in selected

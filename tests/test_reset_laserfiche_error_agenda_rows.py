import importlib.util
import json
import sys
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.modules["llama_cpp"] = MagicMock()

from pipeline.models import AgendaItem, Base, Catalog, Document, Event, Place, SemanticEmbedding


spec = importlib.util.spec_from_file_location(
    "reset_laserfiche_error_agenda_rows",
    Path("scripts/reset_laserfiche_error_agenda_rows.py"),
)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def _fixture(mocker):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    @contextmanager
    def fake_db_session():
        session = Session()
        try:
            yield session
        finally:
            session.close()

    mocker.patch.object(mod, "db_session", fake_db_session)
    mocker.patch.object(mod, "source_aliases_for_city", return_value={"san_mateo"})
    reindex = mocker.patch.object(mod, "reindex_catalog")
    return Session, reindex


def _seed_catalogs(Session):
    session = Session()
    place = Place(
        name="San Mateo",
        state="CA",
        ocd_division_id="ocd-division/country:us/state:ca/place:san_mateo",
        crawler_name="san_mateo",
    )
    session.add(place)
    session.flush()
    event = Event(place_id=place.id, ocd_division_id=place.ocd_division_id, source="san_mateo", name="Agenda")
    session.add(event)
    session.flush()

    polluted = Catalog(
        url_hash="polluted",
        location="/tmp/polluted.html",
        url="https://portal.laserfiche.com/Portal/DocView.aspx?id=1",
        content=(
            "The system has encountered an error and could not complete your request. "
            "If the problem persists, please contact the site administrator."
        ),
        summary="bad summary",
        agenda_segmentation_status="complete",
        agenda_segmentation_item_count=2,
        agenda_segmentation_error=None,
        extraction_status="complete",
        extraction_attempt_count=3,
        processed=True,
    )
    clean = Catalog(
        url_hash="clean",
        location="/tmp/clean.html",
        url="https://portal.laserfiche.com/Portal/DocView.aspx?id=2",
        content="1. CALL TO ORDER\n2. PUBLIC COMMENT\n3. ADJOURNMENT",
        summary=None,
        agenda_segmentation_status=None,
        extraction_status="complete",
        processed=True,
    )
    session.add_all([polluted, clean])
    session.flush()
    session.add_all(
        [
            Document(place_id=place.id, event_id=event.id, catalog_id=polluted.id, category="agenda", url=polluted.url),
            Document(place_id=place.id, event_id=event.id, catalog_id=clean.id, category="agenda", url=clean.url),
            AgendaItem(catalog_id=polluted.id, event_id=event.id, order=1, title="Bad Item"),
            SemanticEmbedding(catalog_id=polluted.id, model_name="test-model", source_hash="bad", embedding=[0.1, 0.2]),
        ]
    )
    session.commit()
    polluted_id = polluted.id
    clean_id = clean.id
    session.close()
    return polluted_id, clean_id


def test_report_counts_matching_laserfiche_error_rows(mocker):
    Session, _reindex = _fixture(mocker)
    polluted_id, _clean_id = _seed_catalogs(Session)

    report = mod._report("san_mateo")

    assert report["matched_total"] == 1
    assert report["matched_complete"] == 1
    assert report["matched_with_items"] == 1
    assert report["matched_with_summary"] == 1
    assert report["sample_catalog_ids"] == [polluted_id]


def test_apply_reset_clears_derived_state_for_matching_rows_only(mocker):
    Session, reindex = _fixture(mocker)
    polluted_id, clean_id = _seed_catalogs(Session)

    result = mod._apply_reset("san_mateo")

    assert result["reset_total"] == 1
    assert result["sample_catalog_ids"] == [polluted_id]
    reindex.assert_called_once_with(polluted_id)

    session = Session()
    polluted = session.get(Catalog, polluted_id)
    clean = session.get(Catalog, clean_id)
    assert polluted.content is None
    assert polluted.summary is None
    assert polluted.agenda_segmentation_status is None
    assert polluted.agenda_segmentation_error is None
    assert polluted.extraction_status == "pending"
    assert polluted.extraction_error == "laserfiche_error_page_detected"
    assert polluted.extraction_attempt_count == 0
    assert polluted.processed is False
    assert session.query(AgendaItem).filter_by(catalog_id=polluted_id).count() == 0
    assert session.query(SemanticEmbedding).filter_by(catalog_id=polluted_id).count() == 0
    assert clean.content is not None
    assert clean.extraction_status == "complete"
    session.close()


def test_main_emits_json_report(mocker, capsys):
    _fixture(mocker)
    mocker.patch.object(mod, "_report", return_value={"city": "san_mateo", "matched_total": 0, "matched_complete": 0, "matched_unresolved": 0, "matched_with_items": 0, "matched_with_summary": 0, "sample_catalog_ids": []})
    mocker.patch.object(sys, "argv", ["reset_laserfiche_error_agenda_rows.py", "--json"])

    exit_code = mod.main()

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["report"]["city"] == "san_mateo"

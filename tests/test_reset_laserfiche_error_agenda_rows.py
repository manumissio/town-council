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
    loading_shell = Catalog(
        url_hash="loading-shell",
        location="/tmp/loading.html",
        url="https://portal.laserfiche.com/Portal/DocView.aspx?id=3",
        content=(
            "[PAGE 1] Loading... The URL can be used to link to this page "
            "Your browser does not support the video tag."
        ),
        summary=None,
        agenda_segmentation_status="empty",
        extraction_status="complete",
        extraction_attempt_count=2,
        processed=True,
    )
    staff_report = Catalog(
        url_hash="staff-report",
        location="/tmp/staff-report.pdf",
        url="https://portal.laserfiche.com/Portal/ElectronicFile.aspx?docid=4",
        content=(
            "CITY OF SAN MATEO\nAgenda Report\nAgenda Number: 8\nSection Name: NEW BUSINESS\n"
            "TO: City Council\nFROM: Alex Khojikian, City Manager\n"
            "SUBJECT: Boards and Commissions Vacancy Process\n"
            "RECOMMENDATION: Approve the revised vacancy process."
        ),
        summary=None,
        agenda_segmentation_status="empty",
        extraction_status="complete",
        extraction_attempt_count=1,
        processed=True,
    )
    summarized_staff_report = Catalog(
        url_hash="staff-report-summarized",
        location="/tmp/staff-report-summarized.pdf",
        url="https://portal.laserfiche.com/Portal/ElectronicFile.aspx?docid=5",
        content=staff_report.content,
        summary="already summarized",
        agenda_segmentation_status="complete",
        agenda_segmentation_item_count=1,
        extraction_status="complete",
        extraction_attempt_count=1,
        processed=True,
    )
    session.add_all([polluted, clean, loading_shell, staff_report, summarized_staff_report])
    session.flush()
    session.add_all(
        [
            Document(place_id=place.id, event_id=event.id, catalog_id=polluted.id, category="agenda", url=polluted.url),
            Document(place_id=place.id, event_id=event.id, catalog_id=clean.id, category="agenda", url=clean.url),
            Document(place_id=place.id, event_id=event.id, catalog_id=loading_shell.id, category="agenda", url=loading_shell.url),
            Document(place_id=place.id, event_id=event.id, catalog_id=staff_report.id, category="agenda", url=staff_report.url),
            Document(place_id=place.id, event_id=event.id, catalog_id=summarized_staff_report.id, category="agenda", url=summarized_staff_report.url),
            AgendaItem(catalog_id=polluted.id, event_id=event.id, order=1, title="Bad Item"),
            SemanticEmbedding(catalog_id=polluted.id, model_name="test-model", source_hash="bad", embedding=[0.1, 0.2]),
        ]
    )
    session.commit()
    polluted_id = polluted.id
    clean_id = clean.id
    loading_shell_id = loading_shell.id
    staff_report_id = staff_report.id
    summarized_staff_report_id = summarized_staff_report.id
    session.close()
    return polluted_id, clean_id, loading_shell_id, staff_report_id, summarized_staff_report_id


def test_report_counts_matching_laserfiche_error_rows(mocker):
    Session, _reindex = _fixture(mocker)
    polluted_id, _clean_id, loading_shell_id, _staff_report_id, _summarized_staff_report_id = _seed_catalogs(Session)

    report = mod._report("san_mateo")

    assert report["matched_total"] == 2
    assert report["matched_complete"] == 1
    assert report["matched_empty"] == 1
    assert report["matched_with_items"] == 1
    assert report["matched_with_summary"] == 1
    assert report["reason_counts"] == {
        "laserfiche_error_page_detected": 1,
        "laserfiche_loading_shell_detected": 1,
    }
    assert report["sample_catalog_ids"] == [polluted_id, loading_shell_id]


def test_report_includes_document_shape_rows_only_with_flag(mocker):
    Session, _reindex = _fixture(mocker)
    _polluted_id, _clean_id, _loading_shell_id, staff_report_id, summarized_staff_report_id = _seed_catalogs(Session)
    mocker.patch.object(mod, "has_viable_structured_agenda_source", return_value=False)

    report = mod._report("san_mateo", include_document_shape=True)

    assert report["matched_total"] == 3
    assert report["family_counts"] == {
        "document_shape": 1,
        "laserfiche": 2,
    }
    assert report["reason_counts"] == {
        "laserfiche_error_page_detected": 1,
        "laserfiche_loading_shell_detected": 1,
        "single_item_staff_report_detected": 1,
    }
    assert staff_report_id in report["sample_catalog_ids"]
    assert summarized_staff_report_id not in report["sample_catalog_ids"]


def test_apply_reset_clears_derived_state_for_matching_rows_only(mocker):
    Session, reindex = _fixture(mocker)
    polluted_id, clean_id, loading_shell_id, _staff_report_id, _summarized_staff_report_id = _seed_catalogs(Session)

    result = mod._apply_reset("san_mateo")

    assert result["reset_total"] == 2
    assert result["reason_counts"] == {
        "laserfiche_error_page_detected": 1,
        "laserfiche_loading_shell_detected": 1,
    }
    assert result["sample_catalog_ids"] == [polluted_id, loading_shell_id]
    assert reindex.call_count == 2

    session = Session()
    polluted = session.get(Catalog, polluted_id)
    clean = session.get(Catalog, clean_id)
    shell = session.get(Catalog, loading_shell_id)
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
    assert shell.content is None
    assert shell.agenda_segmentation_status is None
    assert shell.extraction_error == "laserfiche_loading_shell_detected"
    assert clean.content is not None
    assert clean.extraction_status == "complete"
    session.close()


def test_apply_reset_includes_document_shape_rows_only_with_flag(mocker):
    Session, reindex = _fixture(mocker)
    polluted_id, clean_id, loading_shell_id, staff_report_id, summarized_staff_report_id = _seed_catalogs(Session)
    mocker.patch.object(mod, "has_viable_structured_agenda_source", return_value=False)

    result = mod._apply_reset("san_mateo", include_document_shape=True)

    assert result["reset_total"] == 3
    assert result["family_counts"] == {
        "document_shape": 1,
        "laserfiche": 2,
    }
    assert result["reason_counts"] == {
        "laserfiche_error_page_detected": 1,
        "laserfiche_loading_shell_detected": 1,
        "single_item_staff_report_detected": 1,
    }
    assert result["sample_catalog_ids"] == [polluted_id, loading_shell_id, staff_report_id]
    assert reindex.call_count == 3

    session = Session()
    staff_report = session.get(Catalog, staff_report_id)
    summarized_staff_report = session.get(Catalog, summarized_staff_report_id)
    clean = session.get(Catalog, clean_id)
    assert staff_report.content is None
    assert staff_report.summary is None
    assert staff_report.agenda_segmentation_status is None
    assert staff_report.extraction_status == "pending"
    assert staff_report.extraction_error == "single_item_staff_report_detected"
    assert summarized_staff_report.content is not None
    assert summarized_staff_report.summary == "already summarized"
    assert clean.content is not None
    session.close()


def test_main_emits_json_report(mocker, capsys):
    _fixture(mocker)
    mocker.patch.object(mod, "_report", return_value={"city": "san_mateo", "matched_total": 0, "matched_complete": 0, "matched_empty": 0, "matched_failed": 0, "matched_unresolved": 0, "matched_with_items": 0, "matched_with_summary": 0, "family_counts": {}, "reason_counts": {}, "sample_catalog_ids": []})
    mocker.patch.object(sys, "argv", ["reset_laserfiche_error_agenda_rows.py", "--json"])

    exit_code = mod.main()

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["report"]["city"] == "san_mateo"

import importlib.util
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.modules["llama_cpp"] = MagicMock()
sys.modules["tika"] = MagicMock()

from pipeline.models import AgendaItem, Base, Catalog, Document, Event, Place


spec = importlib.util.spec_from_file_location("segment_city_corpus", Path("scripts/segment_city_corpus.py"))
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


@pytest.fixture
def city_db(mocker):
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
    return Session


def _add_catalog(session, event, place, *, location, content="agenda text", category="agenda", status=None, page_number=None):
    catalog = Catalog(
        url_hash=f"hash-{event.id}-{location}-{session.query(Catalog).count()}",
        location=location,
        content=content,
        agenda_segmentation_status=status,
    )
    session.add(catalog)
    session.flush()
    session.add(
        Document(
            place_id=place.id,
            event_id=event.id,
            catalog_id=catalog.id,
            category=category,
            url=f"https://example.com/{catalog.id}",
        )
    )
    if status == "complete":
        session.add(
            AgendaItem(
                catalog_id=catalog.id,
                event_id=event.id,
                order=1,
                title="Item 1",
                page_number=page_number,
            )
        )
    session.flush()
    return catalog


def test_segment_catalog_subprocess_marks_timeout_failed(mocker):
    timeout_exc = subprocess.TimeoutExpired(cmd=["python"], timeout=5)
    run = mocker.patch.object(mod.subprocess, "run", side_effect=timeout_exc)
    mark_failed = mocker.patch.object(mod, "_mark_catalog_failed")

    outcome, duration_seconds, detail = mod._segment_catalog_subprocess(42, 5)

    run.assert_called_once()
    mark_failed.assert_called_once_with(42, "agenda_segmentation_timeout:5s")
    assert outcome == "timed_out"
    assert duration_seconds >= 0
    assert detail == "agenda_segmentation_timeout:5s"


def test_segment_catalog_subprocess_marks_failed_when_terminal_status_missing(mocker):
    run = mocker.patch.object(mod.subprocess, "run", return_value=mocker.Mock(stdout="", stderr=""))
    mocker.patch.object(mod, "_catalog_status", return_value=None)
    mark_failed = mocker.patch.object(mod, "_mark_catalog_failed")

    outcome, _duration_seconds, detail = mod._segment_catalog_subprocess(43, 5)

    run.assert_called_once()
    mark_failed.assert_called_once_with(43, "agenda_segmentation_missing_terminal_status")
    assert outcome == "failed"
    assert detail == "agenda_segmentation_missing_terminal_status"


def test_segment_city_corpus_continues_after_timeout(mocker, capsys):
    mocker.patch.object(mod, "_catalog_ids_for_city", return_value=[1, 2, 3])
    mocker.patch.object(mod, "_prioritized_catalog_ids", return_value=[1, 2, 3])
    mocker.patch.object(mod, "_catalog_timeout_seconds", return_value=7)
    mocker.patch.object(
        mod,
        "_segment_catalog_subprocess",
        side_effect=[
            ("timed_out", 7.0, "agenda_segmentation_timeout:7s"),
            ("complete", 0.3, None),
            ("empty", 0.2, None),
        ],
    )

    mocker.patch.object(sys, "argv", ["segment_city_corpus.py", "--city", "sunnyvale"])

    exit_code = mod.main()

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "segmented city=sunnyvale catalog_count=3 complete=1 empty=1 failed=0 timed_out=1" in captured.out


def test_segment_city_corpus_reuses_shared_city_aliases():
    assert mod.source_aliases_for_city("san_mateo") == {"san_mateo", "san mateo"}


def test_catalog_ids_for_city_respects_priority_limit_and_resume(city_db):
    session = city_db()
    place = Place(
        name="berkeley",
        state="CA",
        ocd_division_id="ocd-division/country:us/state:ca/place:berkeley",
        crawler_name="berkeley",
    )
    session.add(place)
    session.flush()

    plain_event = Event(place_id=place.id, ocd_division_id=place.ocd_division_id, source="berkeley", name="Plain")
    html_event = Event(place_id=place.id, ocd_division_id=place.ocd_division_id, source="berkeley", name="HTML")
    sibling_event = Event(place_id=place.id, ocd_division_id=place.ocd_division_id, source="berkeley", name="Sibling")
    session.add_all([plain_event, html_event, sibling_event])
    session.flush()

    plain_catalog = _add_catalog(session, plain_event, place, location="/tmp/plain.pdf")
    html_catalog = _add_catalog(session, html_event, place, location="/tmp/current.html")
    sibling_pdf_catalog = _add_catalog(session, sibling_event, place, location="/tmp/sibling.pdf")
    _add_catalog(session, sibling_event, place, location="/tmp/reference.html", content="")
    plain_catalog_id = plain_catalog.id
    html_catalog_id = html_catalog.id
    sibling_pdf_catalog_id = sibling_pdf_catalog.id
    session.commit()
    session.close()

    selected = mod._catalog_ids_for_city("berkeley")
    assert selected == [plain_catalog_id, html_catalog_id, sibling_pdf_catalog_id]

    prioritized = mod._prioritized_catalog_ids("berkeley", selected)
    assert prioritized == [html_catalog_id, sibling_pdf_catalog_id, plain_catalog_id]

    limited = mod._catalog_ids_for_city("berkeley", limit=2)
    assert limited == [plain_catalog_id, html_catalog_id]

    resumed = mod._catalog_ids_for_city("berkeley", resume_after_id=html_catalog_id)
    assert resumed == [sibling_pdf_catalog_id]


def test_catalog_worker_count_clamps_guarded_inprocess(mocker):
    mocker.patch.object(mod, "LOCAL_AI_BACKEND", "inprocess")
    mocker.patch.object(mod, "LOCAL_AI_ALLOW_MULTIPROCESS", False)
    mocker.patch.object(mod, "LOCAL_AI_REQUIRE_SOLO_POOL", True)

    assert mod._catalog_worker_count(4) == 1


def test_segment_catalog_batch_aggregates_parallel_outcomes(mocker):
    mocker.patch.object(
        mod,
        "_segment_catalog_subprocess",
        side_effect=[
            ("complete", 0.2, None),
            ("failed", 0.3, "boom"),
            ("timed_out", 0.4, "timeout"),
        ],
    )
    progress = []

    result = mod._segment_catalog_batch(
        "berkeley",
        [101, 102, 103],
        timeout_seconds=7,
        workers=2,
        progress_callback=lambda city, index, total, catalog_id, outcome, duration: progress.append(
            (city, index, total, catalog_id, outcome, duration)
        ),
    )

    assert result == {
        "city": "berkeley",
        "catalog_count": 3,
        "complete": 1,
        "empty": 0,
        "failed": 1,
        "timed_out": 1,
    }
    assert {entry[3] for entry in progress} == {101, 102, 103}

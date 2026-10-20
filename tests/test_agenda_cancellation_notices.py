from datetime import date
from contextlib import nullcontext
import gzip
import json
import logging
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

import pytest
import requests
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from pipeline.agenda_extraction_fallback import run_agenda_extraction_pipeline
from pipeline.agenda_resolver import resolve_agenda_items
from pipeline.agenda_resolver_contracts import AgendaExtractor
from pipeline import agenda_segmentation_maintenance, agenda_worker, indexer
from pipeline.models import AgendaItem, Catalog, Document, Event, Place
from pipeline.task_agenda_segmentation import run_segment_agenda_task_family


SAMPLE_PATH = Path(__file__).resolve().parents[1] / "experiments/results/agenda_boundary_2026_10_18.json.gz"
CANCELLATION_CATALOG_IDS = (6530, 6961, 8733, 8769)
INVENTED_PROVIDER_BUSINESS = "1: Approve the annual park improvement budget (Page 1) - Adopt the budget."
NOTICE_HEADER = "[PAGE 1]\nCANCELLATION NOTICE\nMEETING CANCELED\n"
BUSINESS_TITLE = "Approve the annual park improvement budget"


@pytest.fixture(params=CANCELLATION_CATALOG_IDS)
def cancellation_text(request: pytest.FixtureRequest) -> str:
    with gzip.open(SAMPLE_PATH, "rt", encoding="utf-8") as sample_stream:
        sample = json.load(sample_stream)
    return next(document["content"] for document in sample["documents"] if document["catalog_id"] == request.param)


@pytest.mark.parametrize("provider_output", [None, INVENTED_PROVIDER_BUSINESS])
def test_cancellation_only_source_produces_no_agenda_items(
    cancellation_text: str, provider_output: str | None,
) -> None:
    agenda_items = run_agenda_extraction_pipeline(
        text=cancellation_text,
        raw_provider_content=provider_output,
        mode="balanced",
        logger=logging.getLogger(__name__),
    )

    assert agenda_items == []


@pytest.fixture
def legistar_http(monkeypatch: pytest.MonkeyPatch) -> None:
    def response_for_url(_session: requests.Session, url: str, **_kwargs: object) -> requests.Response:
        payload = [{"EventId": 42}]
        if url.endswith("/EventItems"):
            payload = [{"EventItemTitle": title, "EventItemMatterId": matter_id} for matter_id, title in (
                (10840, BUSINESS_TITLE), (10837, "Review transportation funding"), (10844, "Adopt the zoning amendment"),
            )]
        response = requests.Response()
        response.status_code = 200
        response._content = json.dumps(payload).encode()
        return response

    monkeypatch.setattr(requests.Session, "get", response_for_url)


def resolve_source(source: str) -> dict[str, object]:
    catalog = Catalog(content=source, location="meeting.pdf")
    event = Event(place=Place(legistar_client="cancellation-regression"), record_date=date(2026, 10, 19))
    document = Document(catalog=catalog, event=event)
    local_ai = Mock(spec=AgendaExtractor)
    local_ai.extract_agenda.return_value = [{"title": BUSINESS_TITLE}]
    with Session(create_engine("sqlite:///:memory:")) as session:
        return resolve_agenda_items(session, catalog, document, local_ai)


def test_cancellation_source_overrides_unrelated_legistar_rows(cancellation_text: str, legistar_http: None) -> None:
    resolved = resolve_source(cancellation_text)

    assert resolved["items"] == []
    assert resolved["llm_fallback_invoked"] is False


@pytest.mark.parametrize("source", [
    f"{NOTICE_HEADER}\nREGULAR MEETING AGENDA\n\n{BUSINESS_TITLE}",
    f"{NOTICE_HEADER}\n[PAGE 2]\nREGULAR MEETING AGENDA\n\n{BUSINESS_TITLE}",
    f"{NOTICE_HEADER}\n1. {BUSINESS_TITLE}\nRecommendation: Adopt the budget.",
    f"{NOTICE_HEADER}\n{BUSINESS_TITLE}\nRecommendation: Adopt the budget.",
    f"{NOTICE_HEADER}\n25-0123 {BUSINESS_TITLE}",
    f"[PAGE 1]\nCANCELLATION NOTICE\n\n{BUSINESS_TITLE}",
])
def test_mixed_or_ambiguous_cancellation_keeps_business(source: str, legistar_http: None) -> None:
    agenda_items = run_agenda_extraction_pipeline(
        text=source, raw_provider_content=None, mode="balanced", logger=logging.getLogger(__name__),
    )

    assert any(BUSINESS_TITLE in str(agenda["title"]) for agenda in agenda_items)
    resolved = resolve_source(source)
    assert resolved["source_used"] == "legistar"
    assert any(agenda["title"] == BUSINESS_TITLE for agenda in resolved["items"])


@pytest.mark.parametrize("entrypoint", ["task", "worker", "maintenance"])
def test_empty_cancellation_clears_previously_stored_rows(
    db_session: Session, monkeypatch: pytest.MonkeyPatch, entrypoint: str,
) -> None:
    place = Place(name="Test City", state="CA", ocd_division_id="cancellation-test")
    event = Event(name="Council meeting", place=place)
    catalog = Catalog(content=f"{NOTICE_HEADER}The next meeting will be announced.",
                      url_hash="cancellation-test", agenda_items_hash="stale-hash")
    document = Document(event=event, place=place, catalog=catalog, category="agenda")
    db_session.add_all([place, event, catalog, document])
    db_session.flush()
    db_session.add(AgendaItem(event_id=event.id, catalog_id=catalog.id, title="City of Test City"))
    db_session.commit()
    search_client = MagicMock()
    search_client.index.return_value.delete_documents.return_value = SimpleNamespace(task_uid=41)
    search_client.wait_for_task.return_value = SimpleNamespace(status="succeeded", error=None)
    monkeypatch.setattr(indexer.meilisearch, "Client", lambda *_args, **_kwargs: search_client)
    local_ai = Mock(spec=AgendaExtractor)
    local_ai.extract_agenda.return_value = []

    if entrypoint == "task":
        run_segment_agenda_task_family(db_session, catalog.id, local_ai=local_ai)
    elif entrypoint == "worker":
        monkeypatch.setattr(agenda_worker, "db_session", lambda: nullcontext(db_session))
        agenda_worker.segment_document_agenda(catalog.id)
    else:
        resolved = resolve_agenda_items(db_session, catalog, document, local_ai)
        agenda_segmentation_maintenance.persist_segmented_agenda(
            db_session, catalog=catalog, doc=document, items_data=resolved["items"],
        )

    db_session.refresh(catalog)
    assert db_session.query(AgendaItem).filter_by(catalog_id=catalog.id).all() == []
    assert catalog.agenda_segmentation_status == "empty"
    assert catalog.agenda_segmentation_item_count == 0
    assert catalog.agenda_items_hash != "stale-hash"

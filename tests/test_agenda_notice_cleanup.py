from datetime import date
import json
import logging
from unittest.mock import Mock

import pytest
import requests
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from pipeline.agenda_extraction_fallback import run_agenda_extraction_pipeline
from pipeline.agenda_resolver import resolve_agenda_items
from pipeline.agenda_resolver_contracts import AgendaExtractor
from pipeline.agenda_service import persist_agenda_items
from pipeline.models import AgendaItem, Base, Catalog, Document, Event, Place


@pytest.mark.parametrize("notice", [
    "MEETING CANCELED",
    "NOTICE OF CANCELLATION",
    "Cancellation Notice",
    "Cancellation Notice - Final",
    "SALUTE TO THE FLAG",
    "PUBLIC HEARINGS/GENERAL BUSINESS",
])
def test_notice_rows_do_not_become_items_beside_live_business(notice: str) -> None:
    agenda_items = run_agenda_extraction_pipeline(
        text=f"[PAGE 1]\n{notice}\n\nApprove the public works contract\n\nAnnual budget report",
        raw_provider_content=None,
        mode="balanced",
        logger=logging.getLogger(__name__),
    )

    titles = [agenda["title"] for agenda in agenda_items]
    assert notice not in titles
    assert "Approve the public works contract" in titles


@pytest.mark.parametrize("title", [
    "Receive the subcommittee cancellation notice",
    "Discuss the canceled hearing and approve the replacement contract",
    "Approve translation services for public meetings",
])
def test_business_mentions_of_notice_words_remain(title: str) -> None:
    agenda_items = run_agenda_extraction_pipeline(
        text=f"[PAGE 1]\n1. {title}\nRecommendation: Approve the proposal.",
        raw_provider_content=None,
        mode="balanced",
        logger=logging.getLogger(__name__),
    )

    assert [agenda["title"] for agenda in agenda_items] == [title]


def test_notice_cleanup_preserves_long_numbered_business() -> None:
    business_title = (
        "Provide feedback on and recommend Council adoption of the draft Fiscal Year "
        "2025-30 Consolidated Plan and Fiscal Year 2025-26 Annual Action Plan for the Human"
    )
    agenda_items = run_agenda_extraction_pipeline(
        text=(
            "[PAGE 1]\n1. SALUTE TO THE FLAG\n\n2. PUBLIC PARTICIPATION OPTIONS\n\n"
            f"3. {business_title}\nRecommendation: Approve the proposal.\n\n"
            "4. Annual budget report\nRecommendation: Receive the report."
        ),
        raw_provider_content=None,
        mode="balanced",
        logger=logging.getLogger(__name__),
    )

    assert [agenda["title"] for agenda in agenda_items] == [business_title, "Annual budget report"]


def test_legistar_cleanup_removes_only_unbacked_wrapper_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    business = [
        {"title": "881 Castro Street - Mixed Use Residential", "legistar_matter_id": 9739},
        {"title": "DPW 17-03 Update Mathilda Avenue Plan Line north of Washington Avenue", "legistar_matter_id": 4824},
        {"title": "Call to Order", "legistar_matter_id": 1234},
        {"title": "Receive the annual traffic report"},
        {"title": "Approve the park improvement budget"},
        {"title": "Review the zoning amendment"},
    ]
    wrappers = [{"title": title} for title in (
        "SALUTE TO THE FLAG", "PUBLIC HEARINGS/GENERAL BUSINESS", "MEETING CANCELED",
        "Public Participation Options", "Translation Link: https://example.org/translation",
    )]

    def legistar_response(_session: requests.Session, url: str, **_kwargs: object) -> requests.Response:
        payload = [{"EventId": 42}]
        if url.endswith("/EventItems"):
            payload = [{
                "EventItemTitle": agenda["title"],
                "EventItemMatterId": agenda.get("legistar_matter_id"),
            } for agenda in business + wrappers]
        response = requests.Response()
        response.status_code = 200
        response._content = json.dumps(payload).encode()
        return response

    monkeypatch.setattr(requests.Session, "get", legistar_response)
    catalog = Catalog(content="", location="meeting.pdf")
    event = Event(record_date=date(2026, 10, 19), place=Place(legistar_client="notice-cleanup-test"))
    document = Document(event=event, catalog=catalog)
    local_ai = Mock(spec=AgendaExtractor)
    local_ai.extract_agenda.return_value = []
    with Session(create_engine("sqlite:///:memory:")) as session:
        resolved = resolve_agenda_items(session, catalog, document, local_ai)

    assert resolved["source_used"] == "legistar"
    assert [agenda["title"] for agenda in resolved["items"]] == [agenda["title"] for agenda in business]
    assert [agenda["legistar_matter_id"] for agenda in resolved["items"]] == [
        agenda.get("legistar_matter_id") for agenda in business
    ]


def test_empty_replacement_removes_old_rows_and_updates_agenda_hash() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        catalog = Catalog(url_hash="notice-test", agenda_items_hash="old-hash")
        event = Event(name="Council meeting", place=Place(name="Test City", state="CA", ocd_division_id="test-city"))
        session.add_all([catalog, event])
        session.flush()
        session.add(AgendaItem(
            ocd_id="old-notice", catalog_id=catalog.id, event_id=event.id,
            title="MEETING CANCELED",
        ))
        session.commit()

        persist_agenda_items(session, catalog.id, event.id, [])
        session.commit()

        assert session.query(AgendaItem).filter_by(catalog_id=catalog.id).all() == []
        assert catalog.agenda_items_hash != "old-hash"

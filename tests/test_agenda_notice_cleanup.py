import logging

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from pipeline.agenda_extraction_fallback import run_agenda_extraction_pipeline
from pipeline.agenda_resolver_legistar_policy import _filter_legistar_items
from pipeline.agenda_service import persist_agenda_items
from pipeline.models import AgendaItem, Base, Catalog, Event, Place


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


def test_legistar_cleanup_removes_only_unbacked_wrapper_rows() -> None:
    business = [
        {"title": "881 Castro Street - Mixed Use Residential", "legistar_matter_id": 9739},
        {"title": "DPW 17-03 Update Mathilda Avenue Plan Line north of Washington Avenue", "legistar_matter_id": 4824},
        {"title": "Call to Order", "legistar_matter_id": 1234, "votes": [{"vote": "yes"}]},
        {"title": "Receive the annual traffic report"},
    ]
    wrappers = [{"title": title} for title in (
        "SALUTE TO THE FLAG", "PUBLIC HEARINGS/GENERAL BUSINESS", "MEETING CANCELED",
        "Public Participation Options", "Translation Link: https://example.org/translation",
    )]

    assert _filter_legistar_items(business + wrappers) == business


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

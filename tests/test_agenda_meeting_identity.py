from datetime import date
import gzip
import json
from pathlib import Path

import pytest
import requests
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from pipeline.agenda_legistar import fetch_legistar_agenda_items
from pipeline.agenda_resolver import has_viable_structured_agenda_source, resolve_agenda_items
from pipeline.models import Catalog, Document, Event, Place


COUNCIL_SOURCE = "https://sunnyvaleca.legistar.com/MeetingDetail.aspx?LEGID=3346&GID=270&G=FA76FAAA-7A74-41EA-9143-F2DB1947F9A5"
PLANNING_SOURCE = "https://sunnyvaleca.legistar.com/MeetingDetail.aspx?LEGID=3194&GID=270&G=FA76FAAA-7A74-41EA-9143-F2DB1947F9A5"
INTERVIEW_TITLE = "Board and Commission Interviews"
WRONG_TITLES = ("Housing Law Training", "Approve Planning Commission Meeting Minutes", "Planning Commission Proposed Study Issues")
SAMPLE_PATH = Path("experiments/results/agenda_boundary_2026_10_18.json.gz")


class InterviewProvider:
    def extract_agenda(self, content: str) -> list[dict[str, object]]:
        return [{"title": INTERVIEW_TITLE, "description": "Interviews for board and commission vacancies"}]


@pytest.fixture
def meeting_transport(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, object]]:
    events: list[dict[str, object]] = [
        {"EventId": 3194, "EventInSiteURL": PLANNING_SOURCE},
        {"EventId": 3346, "EventInSiteURL": COUNCIL_SOURCE},
    ]

    def respond(_session: requests.Session, url: str, **_kwargs: object) -> requests.Response:
        payload: object = events
        if url.endswith("/3194/EventItems"):
            payload = [{"EventItemTitle": title, "EventItemMatterId": order} for order, title in enumerate(WRONG_TITLES, 1)]
        elif url.endswith("/3346/EventItems"):
            payload = [{"EventItemTitle": INTERVIEW_TITLE, "EventItemMatterId": 10061}]
        response = requests.Response()
        response.status_code = 200
        response._content = json.dumps(payload).encode()
        return response

    monkeypatch.setattr(requests.Session, "get", respond)
    return events


def council_document(source_url: str | None = COUNCIL_SOURCE) -> tuple[Catalog, Document]:
    with gzip.open(SAMPLE_PATH, "rt", encoding="utf-8") as sample_stream:
        sample = json.load(sample_stream)
    source = next(document["content"] for document in sample["documents"] if document["catalog_id"] == 3034)
    catalog = Catalog(content=source, location="meeting.pdf")
    event = Event(
        record_date=date(2021, 5, 10), source_url=source_url,
        place=Place(legistar_client="meeting-identity-test"),
    )
    return catalog, Document(catalog=catalog, event=event)


@pytest.mark.parametrize("reverse_events", [False, True])
def test_resolver_never_borrows_another_body_on_the_same_date(
    meeting_transport: list[dict[str, object]], reverse_events: bool,
) -> None:
    if reverse_events:
        meeting_transport.reverse()
    catalog, document = council_document()
    with Session(create_engine("sqlite:///:memory:")) as session:
        resolved = resolve_agenda_items(session, catalog, document, InterviewProvider())

    assert [agenda["title"] for agenda in resolved["items"]] == [INTERVIEW_TITLE]
    assert resolved["legistar_accepted"] is False


@pytest.mark.parametrize("source_url", [None, "https://example.org/missing-meeting"])
def test_missing_meeting_identity_uses_source_content_instead_of_another_event(
    meeting_transport: list[dict[str, object]], source_url: str | None,
) -> None:
    catalog, document = council_document(source_url)
    with Session(create_engine("sqlite:///:memory:")) as session:
        resolved = resolve_agenda_items(session, catalog, document, InterviewProvider())

    assert [agenda["title"] for agenda in resolved["items"]] == [INTERVIEW_TITLE]
    assert resolved["raw_legistar_count"] == 0


def test_duplicate_source_identity_is_not_treated_as_authoritative(
    meeting_transport: list[dict[str, object]],
) -> None:
    meeting_transport[0]["EventInSiteURL"] = COUNCIL_SOURCE
    catalog, document = council_document()
    with Session(create_engine("sqlite:///:memory:")) as session:
        resolved = resolve_agenda_items(session, catalog, document, InterviewProvider())
    assert [agenda["title"] for agenda in resolved["items"]] == [INTERVIEW_TITLE]
    assert resolved["raw_legistar_count"] == 0


def test_structured_source_check_does_not_accept_a_different_meeting(
    meeting_transport: list[dict[str, object]],
) -> None:
    catalog, document = council_document()
    with Session(create_engine("sqlite:///:memory:")) as session:
        assert has_viable_structured_agenda_source(session, catalog, document) is False


def test_exact_meeting_identity_retains_the_correct_matter_link(
    meeting_transport: list[dict[str, object]],
) -> None:
    agenda = fetch_legistar_agenda_items(
        "meeting-identity-test", date(2021, 5, 10), event_source_url=COUNCIL_SOURCE,
    )
    assert [record["title"] for record in agenda] == [INTERVIEW_TITLE]
    assert [record["legistar_matter_id"] for record in agenda] == [10061]


@pytest.mark.parametrize("event_id", [0, True, "3346"])
def test_invalid_matching_event_id_does_not_supply_structured_items(
    meeting_transport: list[dict[str, object]], event_id: object,
) -> None:
    meeting_transport[1]["EventId"] = event_id
    agenda = fetch_legistar_agenda_items(
        "meeting-identity-test", date(2021, 5, 10), event_source_url=COUNCIL_SOURCE,
    )
    assert agenda == []

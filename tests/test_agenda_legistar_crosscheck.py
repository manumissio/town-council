from datetime import date

import requests

from pipeline import agenda_legistar
from pipeline.agenda_legistar import fetch_legistar_agenda_items


class _FakeResponse:
    def __init__(self, payload, status_code=200, text=""):
        self._payload = payload
        self.status_code = status_code
        self.text = text

    def raise_for_status(self):
        if self.status_code >= 400:
            error = requests.HTTPError(f"{self.status_code} error")
            error.response = self
            raise error
        return None

    def json(self):
        return self._payload


class _FakeSession:
    def __init__(self, responses):
        self._responses = responses
        self.calls = []

    def get(self, url, timeout=None):
        self.calls.append((url, timeout))
        return self._responses.pop(0)


def test_fetch_legistar_agenda_items_normalizes_payload():
    session = _FakeSession([
        _FakeResponse([{"EventId": 123}]),
        _FakeResponse([
            {"EventItemTitle": "Budget Amendment", "EventItemAgendaNumber": "1", "EventItemMatterId": 11},
            {"EventItemMatterName": "Public Employee Appointment", "EventItemAgendaNumber": "2", "EventItemMatterId": 12},
        ]),
    ])

    items = fetch_legistar_agenda_items(
        legistar_client="berkeley",
        event_date=date(2026, 2, 8),
        http=session,
    )

    assert len(items) == 2
    assert items[0]["title"] == "Budget Amendment"
    assert items[0]["description"] == "Legistar item 1"
    assert items[0]["legistar_matter_id"] == 11
    assert items[1]["title"] == "Public Employee Appointment"


def test_fetch_legistar_agenda_items_returns_empty_when_unconfigured():
    items = fetch_legistar_agenda_items(legistar_client=None, event_date=None)
    assert items == []


def test_fetch_legistar_agenda_items_memoizes_known_tenant_capability_miss():
    agenda_legistar._LEGISTAR_EVENT_ITEMS_CAPABILITY_CACHE.clear()
    session = _FakeSession([
        _FakeResponse(
            {"Message": "'Agenda Draft Status' or 'Agenda Status Not Vievable By The Public' is not setup in settings. Value should be greater than 0."},
            status_code=400,
            text="'Agenda Draft Status' or 'Agenda Status Not Vievable By The Public' is not setup in settings. Value should be greater than 0.",
        ),
    ])

    first = fetch_legistar_agenda_items(
        legistar_client="sanleandro",
        event_date=date(2026, 3, 10),
        http=session,
    )
    second = fetch_legistar_agenda_items(
        legistar_client="sanleandro",
        event_date=date(2026, 3, 11),
        http=session,
    )

    assert first == []
    assert second == []
    assert agenda_legistar._LEGISTAR_EVENT_ITEMS_CAPABILITY_CACHE["sanleandro"] is False
    assert len(session.calls) == 1
    assert session.calls[0][0].startswith("https://webapi.legistar.com/v1/sanleandro/events?")


def test_fetch_legistar_agenda_items_memoizes_known_event_items_capability_miss():
    agenda_legistar._LEGISTAR_EVENT_ITEMS_CAPABILITY_CACHE.clear()
    session = _FakeSession([
        _FakeResponse([{"EventId": 123}]),
        _FakeResponse(
            {"Message": "'Agenda Draft Status' or 'Agenda Status Not Vievable By The Public' is not setup in settings. Value should be greater than 0."},
            status_code=400,
            text="'Agenda Draft Status' or 'Agenda Status Not Vievable By The Public' is not setup in settings. Value should be greater than 0.",
        ),
        _FakeResponse([{"EventId": 124}]),
    ])

    first = fetch_legistar_agenda_items(
        legistar_client="sanleandro",
        event_date=date(2026, 3, 10),
        http=session,
    )
    second = fetch_legistar_agenda_items(
        legistar_client="sanleandro",
        event_date=date(2026, 3, 11),
        http=session,
    )

    assert first == []
    assert second == []
    assert agenda_legistar._LEGISTAR_EVENT_ITEMS_CAPABILITY_CACHE["sanleandro"] is False
    assert len(session.calls) == 2
    assert session.calls[1][0].endswith("/events/123/EventItems")


def test_fetch_legistar_agenda_items_does_not_memoize_generic_http_400():
    agenda_legistar._LEGISTAR_EVENT_ITEMS_CAPABILITY_CACHE.clear()
    session = _FakeSession([
        _FakeResponse([{"EventId": 123}]),
        _FakeResponse({"Message": "Bad Request"}, status_code=400, text="Bad Request"),
        _FakeResponse([{"EventId": 123}]),
        _FakeResponse({"Message": "Bad Request"}, status_code=400, text="Bad Request"),
    ])

    first = fetch_legistar_agenda_items(
        legistar_client="berkeley",
        event_date=date(2026, 2, 8),
        http=session,
    )
    second = fetch_legistar_agenda_items(
        legistar_client="berkeley",
        event_date=date(2026, 2, 9),
        http=session,
    )

    assert first == []
    assert second == []
    assert "berkeley" not in agenda_legistar._LEGISTAR_EVENT_ITEMS_CAPABILITY_CACHE
    assert len(session.calls) == 4

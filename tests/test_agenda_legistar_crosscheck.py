from datetime import date

from pipeline.agenda_legistar import fetch_legistar_agenda_items


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
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

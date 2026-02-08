from datetime import date
from types import SimpleNamespace

from pipeline import agenda_resolver


def _doc_with_place(legistar_client="berkeley"):
    return SimpleNamespace(
        event_id=1,
        event=SimpleNamespace(
            record_date=date(2026, 2, 8),
            place=SimpleNamespace(legistar_client=legistar_client),
        ),
    )


def test_agenda_quality_score_penalizes_noise():
    noisy = [
        {"title": "Special Closed Meeting 10/03/11", "page_number": 1},
        {"title": "P R O C L A M A T I O N", "page_number": 1},
    ]
    clean = [
        {"title": "Budget Amendment", "page_number": 3},
        {"title": "Public Employee Appointment", "page_number": 4},
    ]
    assert agenda_resolver.agenda_quality_score(clean) > agenda_resolver.agenda_quality_score(noisy)


def test_resolver_prefers_legistar_when_available(mocker):
    mock_session = mocker.MagicMock()
    catalog = SimpleNamespace(content="text", location="/tmp/doc.pdf")
    doc = _doc_with_place()
    local_ai = mocker.MagicMock()
    local_ai.extract_agenda.return_value = [{"title": "Fallback Item", "page_number": 8}]

    mocker.patch.object(agenda_resolver, "_best_html_items_for_event", return_value=[])
    mocker.patch.object(
        agenda_resolver,
        "fetch_legistar_agenda_items",
        return_value=[
            {"title": "Budget Amendment", "page_number": None},
            {"title": "Public Employee Appointment", "page_number": None},
        ],
    )

    resolved = agenda_resolver.resolve_agenda_items(mock_session, catalog, doc, local_ai)
    assert resolved["source_used"] == "legistar"
    assert len(resolved["items"]) == 2


def test_resolver_falls_back_to_html_then_llm(mocker):
    mock_session = mocker.MagicMock()
    catalog = SimpleNamespace(content="text", location="/tmp/doc.pdf")
    doc = _doc_with_place(legistar_client=None)
    local_ai = mocker.MagicMock()
    local_ai.extract_agenda.return_value = [{"title": "LLM Budget Item", "page_number": 7}]

    mocker.patch.object(agenda_resolver, "fetch_legistar_agenda_items", return_value=[])
    mocker.patch.object(
        agenda_resolver,
        "_best_html_items_for_event",
        return_value=[
            {"title": "1. Public Employee Appointment", "page_number": None},
            {"title": "2. Budget Amendment", "page_number": None},
        ],
    )
    resolved_html = agenda_resolver.resolve_agenda_items(mock_session, catalog, doc, local_ai)
    assert resolved_html["source_used"] == "html"

    mocker.patch.object(
        agenda_resolver,
        "_best_html_items_for_event",
        return_value=[{"title": "header", "page_number": 1}],
    )
    resolved_llm = agenda_resolver.resolve_agenda_items(mock_session, catalog, doc, local_ai)
    assert resolved_llm["source_used"] == "llm"

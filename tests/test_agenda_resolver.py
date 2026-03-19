from datetime import date
from types import SimpleNamespace

import pytest

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


@pytest.mark.parametrize(
    ("items", "expected_score"),
    [
        (
            [
                {"title": "COMMUNICATION ACCESS INFORMATION:", "page_number": 1},
                {
                    "title": "Agendas and agenda reports may be accessed via the Internet at http://example.com",
                    "page_number": 1,
                },
                {"title": "Public Employee Appointment", "page_number": 2},
            ],
            1,
        ),
        (
            [
                {"title": "In witness whereof the official seal shall be affixed forthwith", "page_number": 1},
                {"title": "Budget Amendment", "page_number": 3},
                {"title": "Transit Network Update", "page_number": 4},
            ],
            67,
        ),
        (
            [
                {"title": "Leslie Sakai", "page_number": 1},
                {"title": "Kirk McCarthy (2)", "page_number": 1},
                {"title": "Transit Network Update", "page_number": 2},
            ],
            70,
        ),
    ],
)
def test_agenda_quality_score_parity_fixture_set(items, expected_score):
    assert agenda_resolver.agenda_quality_score(items) == expected_score


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
            {"title": "Call to Order", "page_number": None},
            {"title": "Budget Amendment", "page_number": None},
            {"title": "Public Employee Appointment", "page_number": None},
            {"title": "Adjournment", "page_number": None},
            {"title": "Zoning Amendment Hearing", "page_number": None},
        ],
    )

    resolved = agenda_resolver.resolve_agenda_items(mock_session, catalog, doc, local_ai)
    assert resolved["source_used"] == "legistar"
    assert [item["title"] for item in resolved["items"]] == [
        "Budget Amendment",
        "Public Employee Appointment",
        "Zoning Amendment Hearing",
    ]
    local_ai.extract_agenda.assert_not_called()
    assert resolved["llm_fallback_invoked"] is False
    assert resolved["legistar_accepted"] is True


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
    local_ai.extract_agenda.assert_not_called()
    assert resolved_html["llm_fallback_invoked"] is False

    mocker.patch.object(
        agenda_resolver,
        "_best_html_items_for_event",
        return_value=[{"title": "header", "page_number": 1}],
    )
    resolved_llm = agenda_resolver.resolve_agenda_items(mock_session, catalog, doc, local_ai)
    assert resolved_llm["source_used"] == "llm"
    local_ai.extract_agenda.assert_called_once_with("text")
    assert resolved_llm["llm_fallback_invoked"] is True


def test_resolver_rejects_legistar_procedural_only_payload(mocker):
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
            {"title": "Call to Order", "page_number": None},
            {"title": "Roll Call", "page_number": None},
            {"title": "Adjournment", "page_number": None},
        ],
    )

    resolved = agenda_resolver.resolve_agenda_items(mock_session, catalog, doc, local_ai)
    assert resolved["source_used"] == "llm"
    assert resolved["legistar_accepted"] is False
    local_ai.extract_agenda.assert_called_once_with("text")


def test_filter_legistar_items_removes_933_style_wrappers_and_notice_rows():
    items = [
        {"title": "TELECONFERENCE / PUBLIC PARTICIPATION INFORMATION TO HELP STOP THE SPREAD OF COVID-19"},
        {"title": "APPROVAL OF MINUTES"},
        {"title": "Subject: Approve the October 26 Planning Commission minutes"},
        {"title": "PUBLIC HEARINGS"},
        {"title": "Unless there are separate discussions and/or actions requested by council, staff or a member of the public, it is requested that items under the Consent Calendar be acted on simultaneously."},
        {
            "title": "Subject: Consider a development proposal to demolish an existing commercial building and residential unit, remove and replace four (4) protected trees, and construct a mixed-use development."
        },
        {
            "title": "If you challenge the action of the Planning Commission in court, you may be limited to raising only those issues you or someone else raised at the public hearing described in this agenda."
        },
    ]

    filtered = agenda_resolver._filter_legistar_items(items)

    assert [item["title"] for item in filtered] == [
        "Subject: Approve the October 26 Planning Commission minutes",
        "Subject: Consider a development proposal to demolish an existing commercial building and residential unit, remove and replace four (4) protected trees, and construct a mixed-use development.",
    ]


def test_resolver_preserves_substantive_closed_session_legistar_item(mocker):
    mock_session = mocker.MagicMock()
    catalog = SimpleNamespace(content="text", location="/tmp/doc.pdf")
    doc = _doc_with_place()
    local_ai = mocker.MagicMock()
    local_ai.extract_agenda.return_value = []

    mocker.patch.object(agenda_resolver, "_best_html_items_for_event", return_value=[])
    mocker.patch.object(
        agenda_resolver,
        "fetch_legistar_agenda_items",
        return_value=[
            {"title": "5:30 P.M. SPECIAL COUNCIL MEETING (Closed Session)", "page_number": None},
            {
                "title": "Closed Session Held Pursuant to California Government Code Section 54957.6",
                "page_number": None,
            },
            {"title": "Public Hearing on Downtown Plan", "page_number": None},
            {"title": "Adopt Capital Improvement Program", "page_number": None},
        ],
    )

    resolved = agenda_resolver.resolve_agenda_items(mock_session, catalog, doc, local_ai)
    assert resolved["source_used"] == "legistar"
    assert "5:30 P.M. SPECIAL COUNCIL MEETING (Closed Session)" not in [item["title"] for item in resolved["items"]]
    assert "Closed Session Held Pursuant to California Government Code Section 54957.6" in [
        item["title"] for item in resolved["items"]
    ]
    local_ai.extract_agenda.assert_not_called()


def test_resolver_rejects_legistar_when_only_subject_rows_do_not_reach_acceptance_floor(mocker):
    mock_session = mocker.MagicMock()
    catalog = SimpleNamespace(content="text", location="/tmp/doc.pdf")
    doc = _doc_with_place()
    local_ai = mocker.MagicMock()
    local_ai.extract_agenda.return_value = [{"title": "LLM Budget Item", "page_number": 7}]

    mocker.patch.object(agenda_resolver, "_best_html_items_for_event", return_value=[])
    mocker.patch.object(
        agenda_resolver,
        "fetch_legistar_agenda_items",
        return_value=[
            {"title": "CONSENT CALENDAR", "page_number": None},
            {"title": "Subject: Approve the October 26 Planning Commission minutes", "page_number": None},
            {"title": "PUBLIC HEARINGS", "page_number": None},
            {
                "title": "If you challenge the action of the Planning Commission in court, you may be limited to raising only those issues you or someone else raised at the public hearing described in this agenda.",
                "page_number": None,
            },
            {
                "title": "Subject: Consider a development proposal to demolish an existing commercial building and residential unit, remove and replace four (4) protected trees, and construct a mixed-use development.",
                "page_number": None,
            },
        ],
    )

    resolved = agenda_resolver.resolve_agenda_items(mock_session, catalog, doc, local_ai)
    assert resolved["source_used"] == "llm"
    assert resolved["legistar_accepted"] is False
    local_ai.extract_agenda.assert_called_once_with("text")

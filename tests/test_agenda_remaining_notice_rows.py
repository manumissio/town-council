import gzip
import json
import logging
from pathlib import Path

import pytest

from pipeline.agenda_extraction_fallback import run_agenda_extraction_pipeline


FROZEN_SAMPLE = Path("experiments/results/agenda_boundary_2026_10_18.json.gz")


@pytest.mark.parametrize("header", [
    "City of Example\n\nMeeting Minutes\n\nCity Council",
    "City Council: Community Meeting Notice\n\nCity of Example\n\nNotice and Agenda",
])
def test_opening_metadata_before_document_label_is_not_business(header: str) -> None:
    agenda = run_agenda_extraction_pipeline(
        text=f"[PAGE 1]\n{header}\n\nAnnual budget report\nRecommendation: Receive it.",
        raw_provider_content=None, mode="balanced", logger=logging.getLogger(__name__),
    )

    assert [entry["title"] for entry in agenda] == ["Annual budget report"]


@pytest.mark.parametrize("topic", [
    "City of Example infrastructure investment plan",
    "City Council Budget Report",
    "7:00 PM Transit service expansion",
    "Appoint members to the Library Board",
    "Report from the Planning Commission",
])
@pytest.mark.parametrize("body", ["", "\nRecommendation: Receive it."])
@pytest.mark.parametrize("notice", ["", "City Council: Community Meeting Notice\n\n"])
def test_opening_business_is_not_treated_as_a_document_header(topic: str, body: str, notice: str) -> None:
    agenda = run_agenda_extraction_pipeline(
        text=f"[PAGE 1]\n{notice}{topic}{body}\n\nAnnual budget report",
        raw_provider_content=None, mode="balanced", logger=logging.getLogger(__name__),
    )

    assert [entry["title"] for entry in agenda] == [topic, "Annual budget report"]


@pytest.mark.parametrize("title", ["City of Example", "City Council: Community Meeting Notice"])
@pytest.mark.parametrize("record_anchor", ["", "25-0131\n"])
def test_body_backed_item_is_not_removed_by_header_evidence(title: str, record_anchor: str) -> None:
    agenda = run_agenda_extraction_pipeline(
        text=(f"[PAGE 1]\n{title}\n{record_anchor}Recommendation: Adopt the infrastructure plan."
              "\n\nMeeting Minutes\n\nAnnual budget report"),
        raw_provider_content=None, mode="balanced", logger=logging.getLogger(__name__),
    )

    assert [entry["title"] for entry in agenda] == [title, "Annual budget report"]
    assert "Adopt the infrastructure plan" in agenda[0]["description"]


@pytest.mark.parametrize("intervening", ["Budget", "Unrelated source detail " * 50])
def test_filtered_paragraphs_do_not_create_header_adjacency(intervening: str) -> None:
    topic = "City of Example infrastructure investment plan"
    agenda = run_agenda_extraction_pipeline(
        text=f"[PAGE 1]\n{topic}\n\n{intervening}\n\nMeeting Minutes\n\nAnnual budget report",
        raw_provider_content=None, mode="balanced", logger=logging.getLogger(__name__),
    )

    assert [entry["title"] for entry in agenda] == [topic, "Annual budget report"]


@pytest.mark.parametrize("introduction, list_entry", [
    ("A quorum of the following meeting bodies may attend:", "Planning Commission"),
    ("Council interviewed the following applicants for vacancies.", "Jane Smith - Planning Commission"),
])
def test_notice_does_not_carry_list_context_into_independent_business(introduction: str, list_entry: str) -> None:
    topic = "Report from the Planning Commission"
    agenda = run_agenda_extraction_pipeline(
        text=(f"[PAGE 1]\n{introduction}\n\n{list_entry}\n\n"
              f"City Council: Community Meeting Notice\n\n{topic}\n\nAnnual budget report"),
        raw_provider_content=None, mode="balanced", logger=logging.getLogger(__name__),
    )

    assert [entry["title"] for entry in agenda] == [topic, "Annual budget report"]


@pytest.mark.parametrize(("catalog_id", "expected_title"), [
    (3034, "Board and Commission Interviews"),
    (6655, '"Less Traffic, Better Places: How Do We Get There?"'),
])
def test_frozen_single_topic_records_do_not_publish_metadata_as_business(catalog_id: int, expected_title: str) -> None:
    with gzip.open(FROZEN_SAMPLE, "rt", encoding="utf-8") as source_stream:
        documents = json.load(source_stream)["documents"]
    source = next(document["content"] for document in documents if document["catalog_id"] == catalog_id)
    agenda = run_agenda_extraction_pipeline(
        text=source, raw_provider_content=None, mode="balanced", logger=logging.getLogger(__name__),
    )
    assert [entry["title"] for entry in agenda] == [expected_title]


@pytest.mark.parametrize("topic", [
    "Annual budget report",
    "Discuss Heritage Park improvements - Planning Commission",
    "Approve transit service starting at 7:00 PM",
])
def test_business_after_an_applicant_list_remains_eligible(topic: str) -> None:
    agenda = run_agenda_extraction_pipeline(
        text=("[PAGE 1]\n21-0115 Board and Commission Interviews\n\n"
              "Council interviewed the following applicants for vacancies on boards and commissions:\n\n"
              "Jane Smith - Planning Commission\n\nCommission (Category One)\n\n"
              f"{topic}\nRecommendation: Receive the report."),
        raw_provider_content=None, mode="balanced", logger=logging.getLogger(__name__),
    )
    assert [entry["title"] for entry in agenda] == ["Board and Commission Interviews", topic]


def test_named_business_outside_list_context_is_not_an_attendance_row() -> None:
    agenda = run_agenda_extraction_pipeline(
        text="[PAGE 1]\nCity Council Budget Report\nRecommendation: Receive it.\n\nAnnual budget report",
        raw_provider_content=None, mode="balanced", logger=logging.getLogger(__name__),
    )
    assert [entry["title"] for entry in agenda] == ["City Council Budget Report", "Annual budget report"]


@pytest.mark.parametrize(("topic", "introduction", "list_entry"), [
    (
        "Commission appointment report",
        "Council interviewed the following applicants for vacancies.",
        "Jane Smith - Planning Commission",
    ),
    (
        "Commission appointment report",
        "Council interviewed the following\napplicants for vacancies.",
        "Jane Smith - Planning Commission",
    ),
    (
        "Community meeting report",
        "A quorum of the following meeting bodies may attend:",
        "Planning Commission",
    ),
])
def test_business_title_before_list_narrative_survives(
    topic: str, introduction: str, list_entry: str,
) -> None:
    agenda = run_agenda_extraction_pipeline(
        text=f"[PAGE 1]\n{topic}\n{introduction}\n\n{list_entry}\n\nAnnual budget report",
        raw_provider_content=None, mode="balanced", logger=logging.getLogger(__name__),
    )
    assert [entry["title"] for entry in agenda] == [topic, "Annual budget report"]
    assert agenda[0]["description"] == " ".join(f"{topic}\n{introduction}".split())


@pytest.mark.parametrize(("introduction", "list_entry"), [
    (
        "Council members\ninterviewed the following applicants for vacancies.",
        "Jane Smith - Planning Commission",
    ),
    (
        "Members are advised that a\nquorum of the following meeting bodies may attend:",
        "Planning Commission",
    ),
])
def test_wrapped_list_introductions_do_not_become_business(
    introduction: str, list_entry: str,
) -> None:
    agenda = run_agenda_extraction_pipeline(
        text=f"[PAGE 1]\n{introduction}\n\n{list_entry}\n\nAnnual budget report",
        raw_provider_content=None, mode="balanced", logger=logging.getLogger(__name__),
    )
    assert [entry["title"] for entry in agenda] == ["Annual budget report"]


def test_applicant_details_cross_page_but_do_not_swallow_a_new_unanchored_topic() -> None:
    agenda = run_agenda_extraction_pipeline(
        text=("[PAGE 1]\n21-0115 Board and Commission Interviews\n\n"
              "Council interviewed the following applicants for vacancies on boards and commissions:\n\n"
              "Jane Smith - Planning Commission\n[PAGE 2]\nJohn Jones - Board of Library Trustees\n\n"
              "Annual budget report"),
        raw_provider_content=None, mode="balanced", logger=logging.getLogger(__name__),
    )
    assert [entry["title"] for entry in agenda] == ["Board and Commission Interviews", "Annual budget report"]


def test_hyphenated_business_after_applicants_does_not_need_a_record_id_or_body_field() -> None:
    agenda = run_agenda_extraction_pipeline(
        text=("[PAGE 1]\n21-0115 Board and Commission Interviews\n\n"
              "Council interviewed the following applicants for vacancies on boards and commissions:\n\n"
              "Jane Smith - Planning Commission\n\nWater Rates - Proposed Increase"),
        raw_provider_content=None, mode="balanced", logger=logging.getLogger(__name__),
    )
    assert [entry["title"] for entry in agenda] == [
        "Board and Commission Interviews", "Water Rates - Proposed Increase",
    ]


def test_business_with_a_governing_body_suffix_ends_the_applicant_list() -> None:
    topic = "Discuss Heritage Park improvements - Planning Commission"
    agenda = run_agenda_extraction_pipeline(
        text=("[PAGE 1]\n21-0115 Board and Commission Interviews\n\n"
              "Council interviewed the following applicants for vacancies on boards and commissions:\n\n"
              "Jane Smith - Planning Commission\n\n"
              f"{topic}\n\nAnnual budget report"),
        raw_provider_content=None, mode="balanced", logger=logging.getLogger(__name__),
    )
    assert [entry["title"] for entry in agenda] == [
        "Board and Commission Interviews", topic, "Annual budget report",
    ]


@pytest.mark.parametrize("topic", [
    "7:00 PM Transit service expansion",
    "5:00 PM Review Planning Commission meeting procedures",
])
def test_timed_business_after_a_document_header_is_not_a_schedule(topic: str) -> None:
    agenda = run_agenda_extraction_pipeline(
        text=f"[PAGE 1]\nMeeting Minutes\n\n{topic}\n\nAnnual budget report",
        raw_provider_content=None, mode="balanced", logger=logging.getLogger(__name__),
    )
    assert [entry["title"] for entry in agenda] == [topic, "Annual budget report"]


@pytest.mark.parametrize("meeting_body", ["Council", "City Council", "Planning Commission", "Regular City Council"])
def test_schedule_header_does_not_damage_or_replace_business(meeting_body: str) -> None:
    agenda = run_agenda_extraction_pipeline(
        text=f"[PAGE 1]\nMeeting Minutes\n\nCity of Example\n\n5:00 PM {meeting_body} Meeting\n\nAnnual budget report",
        raw_provider_content=None, mode="balanced", logger=logging.getLogger(__name__),
    )
    assert [entry["title"] for entry in agenda] == ["Annual budget report"]


def test_ocr_spacing_duplicates_collapse_without_merging_other_topics() -> None:
    title = '"Less Traffic, Better Places: How Do We Get There?"'
    agenda = run_agenda_extraction_pipeline(
        text=f"[PAGE 1]\n{title}\n\nLESS TRAFFIC, BETTER PLACES: HOWDOWEGET THERE?\n\nAnnual budget report",
        raw_provider_content=None, mode="balanced", logger=logging.getLogger(__name__),
    )
    assert [entry["title"] for entry in agenda] == [title, "Annual budget report"]


def test_legal_tail_heading_after_adjournment_stops_footer_not_business() -> None:
    agenda = run_agenda_extraction_pipeline(
        text=("[PAGE 1]\n1. Adopt the transit plan\nRecommendation: Adopt it.\n"
              "ADJOURNMENT\nNOTICE TO THE PUBLIC\nCity Clerk\n"
              "Notification of 48 hours prior to the meeting will enable the City to make\n\n"
              "FREE EVENT SPONSORED BY\n\nSponsor information"),
        raw_provider_content=None, mode="balanced", logger=logging.getLogger(__name__),
    )
    assert [entry["title"] for entry in agenda] == ["Adopt the transit plan"]


def test_equivalent_notice_headings_do_not_count_as_two_legal_tail_signals() -> None:
    agenda = run_agenda_extraction_pipeline(
        text=("[PAGE 1]\n1. Adopt the transit plan.\nADJOURNMENT\n"
              "PUBLIC NOTICE\nNOTICE TO THE PUBLIC\n2. Discuss the annual budget"),
        raw_provider_content=None, mode="balanced", logger=logging.getLogger(__name__),
    )
    assert [entry["title"] for entry in agenda] == ["Adopt the transit plan.", "Discuss the annual budget"]

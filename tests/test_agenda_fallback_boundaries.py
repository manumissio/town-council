import logging
from hashlib import sha256

import pytest

from pipeline.agenda_extraction_fallback import run_agenda_extraction_pipeline
from pipeline.agenda_extraction_parser import AgendaItemPayload
from pipeline.config import AGENDA_FALLBACK_MAX_ITEMS_PER_DOC


def extract(source: str, provider_output: str | None = None) -> list[AgendaItemPayload]:
    return run_agenda_extraction_pipeline(
        text=source,
        raw_provider_content=provider_output,
        mode="balanced",
        logger=logging.getLogger(__name__),
    )


@pytest.mark.parametrize("item_heading", ["5.1", "5.1.", "1.A", "1A."])
@pytest.mark.parametrize("separator", [" ", "\n\n"])
def test_item_markers_keep_business_below_section_headings(item_heading: str, separator: str) -> None:
    section = "5. NEW BUSINESS" if item_heading.startswith("5") else "1. CONSENT CALENDAR"
    source = (
        f"[PAGE 1]\n{section}\n\n"
        f"{item_heading}{separator}Approve the public works contract\n"
        "Recommendation:\nApprove the contract for $250,000.\n"
    )

    agenda_items = extract(source)

    assert [agenda_item["title"] for agenda_item in agenda_items] == ["Approve the public works contract"]
    assert "$250,000" in str(agenda_items[0]["description"])


def test_wrapped_numbered_title_keeps_all_lines_but_not_recommendation() -> None:
    source = (
        "[PAGE 2]\n1. Discussion and Prioritization of Issues to Study for Potential\n\n"
        "Amendments to the Sunnyvale City Charter\n\n"
        "for the next election\n\n"
        "Recommendation: Receive the report.\n"
        "2. Approve the public works contract\nRecommendation: Approve the contract.\n"
    )

    agenda_items = extract(source)

    assert agenda_items[0]["title"] == (
        "Discussion and Prioritization of Issues to Study for Potential "
        "Amendments to the Sunnyvale City Charter for the next election"
    )
    assert "Receive the report" in str(agenda_items[0]["description"])
    assert "public works contract" not in str(agenda_items[0]["description"])
    assert agenda_items[0]["page_number"] == 2
    assert len(agenda_items) == 2


def test_record_id_keeps_wrapped_lines_within_one_source_paragraph() -> None:
    source = (
        "[PAGE 1]\nPUBLIC HEARING/GENERAL BUSINESS\n\n"
        "Discussion and Prioritization of Issues to Study for Potential\n"
        "Amendments to the Sunnyvale City Charter\n\n25-03822\n\n"
        "Recommendation: This item is for discussion; staff makes no recommendation.\n\n"
        "Discussion of Subcommittee Assignments, Next Steps and\nDeliverables\n\n25-03843\n"
    )

    titles = [agenda_item["title"] for agenda_item in extract(source)]

    assert "Discussion and Prioritization of Issues to Study for Potential Amendments to the Sunnyvale City Charter" in titles
    assert "Discussion of Subcommittee Assignments, Next Steps and Deliverables" in titles
    assert "Amendments to the Sunnyvale City Charter" not in titles
    assert "Deliverables" not in titles


def test_unmarked_business_is_not_lost_when_another_title_has_a_record_id() -> None:
    source = (
        "[PAGE 1]\nRegional Transit Agreement Update\n\n"
        "Recommendation: Receive the transit report.\n\n"
        "Discussion of Subcommittee Assignments, Next Steps and\nDeliverables\n\n25-03843\n"
    )

    titles = [agenda_item["title"] for agenda_item in extract(source)]

    assert "Regional Transit Agreement Update" in titles
    assert "Discussion of Subcommittee Assignments, Next Steps and Deliverables" in titles


def test_individual_item_cancellation_does_not_hide_other_business() -> None:
    source = (
        "[PAGE 1]\n1. Public hearing on the zoning amendment\n"
        "This hearing is canceled; the council meeting will proceed.\n"
        "2. Approve the public works contract\nRecommendation: Approve the contract.\n"
    )

    assert any("public works contract" in str(agenda_item["title"]) for agenda_item in extract(source))


def test_cancellation_notice_inside_a_live_agenda_does_not_cancel_the_document() -> None:
    source = (
        "[PAGE 1]\n1. Receive the subcommittee cancellation notice\n"
        "Notice of Cancellation\nMEETING CANCELED\n"
        "2. Approve the public works contract\nRecommendation: Approve the contract.\n"
    )

    assert any("public works contract" in str(agenda_item["title"]) for agenda_item in extract(source))


def test_record_id_does_not_join_complete_unrelated_sentences() -> None:
    source = (
        "[PAGE 1]\nReceive the annual budget report.\n\n"
        "Approve the public works contract\n\n25-03843\n"
    )

    titles = [str(agenda_item["title"]) for agenda_item in extract(source)]

    assert "Receive the annual budget report." in titles
    assert "Approve the public works contract" in titles
    assert all(not ("budget" in title and "contract" in title) for title in titles)


def test_explicit_page_marker_is_not_part_of_the_first_paragraph_title() -> None:
    agenda_items = extract(
        "[PAGE 3]\nRegional Transit Agreement Update\n\nApprove the public works contract\n\nAnnual budget report"
    )

    assert agenda_items[0]["title"] == "Regional Transit Agreement Update"
    assert agenda_items[0]["page_number"] == 3


@pytest.mark.parametrize("subitem_marker", ["1A.", "1.A"])
def test_record_id_distinguishes_business_from_nested_recommendations(subitem_marker: str) -> None:
    source = (
        "[PAGE 1]\n1. Subject: Regional Mobility Package\n"
        "Recommendation: Conduct a hearing and take the following action:\n"
        f"{subitem_marker} Contract amendment for corridor upgrades\n"
        f"{subitem_marker} 25-0384 Approve the separate public works contract\n"
        "Recommendation: Approve the contract.\n"
    )

    titles = [str(agenda_item["title"]) for agenda_item in extract(source)]

    assert any("Regional Mobility Package" in title for title in titles)
    assert any("separate public works contract" in title for title in titles)
    assert all("corridor upgrades" not in title for title in titles)


def test_record_identifier_is_not_mistaken_for_a_street_address() -> None:
    agenda_items = extract(
        "[PAGE 1]\n2. 17-0731 Mary Avenue Overcrossing Update\n"
        "Recommendation: Receive the transportation project update.\n"
    )

    assert [agenda_item["title"] for agenda_item in agenda_items] == ["Mary Avenue Overcrossing Update"]


def test_record_anchored_title_preserves_internal_newlines() -> None:
    agenda_items = extract(
        "[PAGE 1]\nPUBLIC HEARING/GENERAL BUSINESS\n\nDiscussion and Prioritization of Issues to Study for Potential\n"
        "Amendments to the Sunnyvale City Charter\n\n25-03822\n"
    )

    assert any(
        agenda_item["title"] == (
            "Discussion and Prioritization of Issues to Study for Potential Amendments to the Sunnyvale City Charter"
        )
        for agenda_item in agenda_items
    )


def test_unanchored_blank_paragraph_is_description_not_title() -> None:
    agenda_items = extract(
        "[PAGE 1]\n1. Approve the public works\ncontract for the central bridge\n\n"
        "Staff recommends awarding the construction contract.\n"
    )

    assert agenda_items[0]["title"] == "Approve the public works contract for the central bridge"
    assert "Staff recommends" in str(agenda_items[0]["description"])


def test_new_section_ends_previous_parent_context() -> None:
    agenda_items = extract(
        "[PAGE 1]\n1. Subject: Regional Transit Agreement\n"
        "Recommendation: Receive the report.\n"
        "2. CONSENT CALENDAR\n"
        "2A. Approve the public works contract\nRecommendation: Approve the contract.\n"
        "2B. Adopt the annual budget amendment\nRecommendation: Adopt the amendment.\n"
    )

    titles = [str(agenda_item["title"]) for agenda_item in agenda_items]
    assert any("Regional Transit Agreement" in title for title in titles)
    assert "Approve the public works contract" in titles
    assert "Adopt the annual budget amendment" in titles


@pytest.mark.parametrize("title", ["Selection of Chair", "Selection of Vice Chair", "Election of Officers"])
def test_record_anchored_elections_are_not_mistaken_for_speakers(title: str) -> None:
    agenda_items = extract(
        f"[PAGE 1]\nORAL COMMUNICATIONS\n2. 23-0777 {title}\n"
        "Chair Sharma called for nominations. Commissioner Johnson was nominated.\n"
    )

    assert any(str(agenda_item["title"]).startswith(title) for agenda_item in agenda_items)


def test_title_before_bare_decimal_marker_is_not_replaced_by_a_field_label() -> None:
    agenda_items = extract(
        "[PAGE 1]\n5. UNFINISHED BUSINESS\n\nTeen Wellness Retreat Feedback\n\n"
        "5.1\n\nRecommendation:\n\nReceive the feedback and discuss future improvements.\n"
    )

    assert [agenda_item["title"] for agenda_item in agenda_items] == ["Teen Wellness Retreat Feedback"]


def test_record_anchored_presentation_before_numbered_items_is_not_lost() -> None:
    agenda_items = extract(
        "[PAGE 1]\nCity of Sunnyvale\n\n"
        "16-0540 PRESENTATION - Mathilda and US 101/SR 237 Project\n\n"
        "1A. 16-0541 Approve the commission meeting minutes\nRecommendation: Approve the minutes.\n"
    )

    titles = [str(agenda_item["title"]) for agenda_item in agenda_items]
    assert any("Mathilda and US 101/SR 237 Project" in title for title in titles)
    assert any("Approve the commission meeting minutes" in title for title in titles)
    assert "City of Sunnyvale" not in titles


@pytest.mark.parametrize("page_break", ["\n", "\n[PAGE 2]\n"])
def test_lettered_business_owns_recommendations_but_not_its_sibling(page_break: str) -> None:
    agenda_items = extract(
        "[PAGE 1]\n1. CONSENT CALENDAR\n"
        "1A. 25-0101 Approve the bridge improvement plan\n"
        "Recommendation: Take the following action:\n"
        "2. Authorize the construction contract amendment\n"
        f"{page_break}1B. Adopt the annual budget amendment\nRecommendation: Adopt the amendment.\n"
    )

    titles = [str(agenda_item["title"]) for agenda_item in agenda_items]
    assert "Approve the bridge improvement plan" in titles
    assert "Adopt the annual budget amendment" in titles
    assert all("Authorize the construction contract amendment" not in title for title in titles)


def test_anchored_prefix_and_numbered_items_share_the_document_budget() -> None:
    alphabetic_digits = str.maketrans("0123456789abcdef", "bcefghjklmnqvxyz")
    first_page = "\n".join(
        f"{index % 99 + 1}. Approve {sha256(str(index).encode()).hexdigest().translate(alphabetic_digits)} project"
        for index in range(AGENDA_FALLBACK_MAX_ITEMS_PER_DOC - 1)
    )
    agenda_items = extract(
        f"[PAGE 1]\n{first_page}\n[PAGE 2]\n"
        "25-0101 Presentation of the annual capital improvement plan\n\n"
        "1. Adopt the annual budget amendment\nRecommendation: Adopt the amendment.\n"
    )

    assert len(agenda_items) == AGENDA_FALLBACK_MAX_ITEMS_PER_DOC
    assert not any("annual budget amendment" in str(agenda_item["title"]) for agenda_item in agenda_items)


def test_standalone_record_id_keeps_its_prefix_business_before_numbered_items() -> None:
    titles = [str(agenda_item["title"]) for agenda_item in extract(
        "[PAGE 1]\nRegional Transit Agreement Update\n\n25-03843\n\n"
        "1. Approve the public works contract\nRecommendation: Approve the contract.\n"
    )]

    assert "Regional Transit Agreement Update" in titles
    assert "Approve the public works contract" in titles


def test_source_record_id_does_not_swallow_a_masthead_or_other_business() -> None:
    titles = [str(agenda_item["title"]) for agenda_item in extract(
        "[PAGE 1]\nCity of Sunnyvale\n\nRegional Transit Agreement Update\n\n"
        "Approve the public works contract\n\n25-03843\n"
    )]

    assert "Regional Transit Agreement Update" in titles
    assert "Approve the public works contract" in titles
    assert all(not ("Sunnyvale" in title and "contract" in title) for title in titles)


@pytest.mark.parametrize("provider_output", [None, "1: Regional Transit Agreement Update (Page 1) - Approve the regional transit agreement."])
def test_attached_cancellation_notice_does_not_suppress_live_provider_business(provider_output: str | None) -> None:
    source = (
        "[PAGE 1]\nRegional Transit Agreement Update\nRecommendation: Approve the agreement.\n\n"
        "[PAGE 2]\nSubcommittee attachment\nNotice of Cancellation\nMEETING CANCELED\n"
    )
    assert any("Regional Transit Agreement" in str(agenda_item["title"])
               for agenda_item in extract(source, provider_output))


def test_record_ids_without_a_preceding_paragraph_are_not_agenda_items() -> None:
    assert extract("[PAGE 1]\n\n25-1234567890\n\n25-1234567891\n") == []


def test_record_id_preserves_a_field_led_title() -> None:
    agenda_items = extract("[PAGE 1]\nSubject: Regional Transit Agreement Update\n\n25-03843\n\n"
                           "1. Approve the public works contract\nRecommendation: Approve the contract.")
    assert any("Regional Transit Agreement" in str(agenda_item["title"]) for agenda_item in agenda_items)

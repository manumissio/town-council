import logging

import pytest

from pipeline.agenda_extraction_fallback import run_agenda_extraction_pipeline


@pytest.mark.parametrize("child_marker", ["1A.", "1.1."])
def test_uppercase_business_parent_is_not_a_section_heading(child_marker: str) -> None:
    agenda_items = run_agenda_extraction_pipeline(
        text=f"1. APPROVE THE PUBLIC WORKS CONTRACT\n{child_marker} Adopt the related amendment",
        raw_provider_content=None,
        mode="balanced",
        logger=logging.getLogger(__name__),
    )

    assert agenda_items[0]["title"] == "APPROVE THE PUBLIC WORKS CONTRACT"


@pytest.mark.parametrize("section", ["NEW BUSINESS", "UNFINISHED BUSINESS", "CONSENT CALENDAR"])
@pytest.mark.parametrize("word_separator", [" ", "\u00a0"])
def test_known_section_heading_is_not_business(section: str, word_separator: str) -> None:
    section = section.replace(" ", word_separator)
    agenda_items = run_agenda_extraction_pipeline(
        text=f"1. {section}\n1.1. Approve the public works contract\nRecommendation: Approve it.",
        raw_provider_content=None,
        mode="balanced",
        logger=logging.getLogger(__name__),
    )

    assert [agenda_item["title"] for agenda_item in agenda_items] == ["Approve the public works contract"]


@pytest.mark.parametrize("marker_gap", ["\n", "\n\n", "\n \n"])
def test_title_before_decimal_marker_keeps_only_its_complete_source_paragraph(marker_gap: str) -> None:
    agenda_items = run_agenda_extraction_pipeline(
        text=(
            "Earlier unrelated business\n\n"
            "Discussion and Prioritization of Issues to Study for Potential\n"
            f"Amendments to the Sunnyvale City Charter{marker_gap}5.1\nRecommendation: Receive the report."
        ),
        raw_provider_content=None,
        mode="balanced",
        logger=logging.getLogger(__name__),
    )

    assert [agenda_item["title"] for agenda_item in agenda_items] == [
        "Discussion and Prioritization of Issues to Study for Potential Amendments to the Sunnyvale City Charter"
    ]


def test_title_normalization_does_not_absorb_an_existing_numbered_item_or_field() -> None:
    agenda_items = run_agenda_extraction_pipeline(
        text=(
            "1. Approve the public works contract\nRecommendation: Approve the contract.\n"
            "Discussion of the City Charter amendments\n5.1\nRecommendation: Receive the report."
        ),
        raw_provider_content=None,
        mode="balanced",
        logger=logging.getLogger(__name__),
    )

    assert [agenda_item["title"] for agenda_item in agenda_items] == [
        "Approve the public works contract", "Discussion of the City Charter amendments"
    ]


def test_title_before_decimal_marker_preserves_nonbreaking_space_indentation() -> None:
    agenda_items = run_agenda_extraction_pipeline(
        text=(
            "Discussion and Prioritization of Issues to Study for Potential\n"
            "\u00a0Amendments to the Sunnyvale City Charter\n5.1\nRecommendation: Receive the report."
        ),
        raw_provider_content=None,
        mode="balanced",
        logger=logging.getLogger(__name__),
    )

    assert [agenda_item["title"] for agenda_item in agenda_items] == [
        "Discussion and Prioritization of Issues to Study for Potential Amendments to the Sunnyvale City Charter"
    ]


@pytest.mark.parametrize("first_item,expected_first_title", [
    ("First agenda item title\n5.1\nRecommendation:\nReceive the report.", "First agenda item title"),
    ("1. First agenda item title.\nReceive the report.", "First agenda item title."),
])
def test_prior_item_body_is_not_part_of_a_later_bare_marker_title(first_item: str, expected_first_title: str) -> None:
    agenda_items = run_agenda_extraction_pipeline(
        text=f"{first_item}\nSecond agenda item title\n5.2\nRecommendation: Receive the next report.",
        raw_provider_content=None,
        mode="balanced",
        logger=logging.getLogger(__name__),
    )

    assert [agenda_item["title"] for agenda_item in agenda_items] == [
        expected_first_title, "Second agenda item title"
    ]

import logging

import pytest

from pipeline.agenda_extraction_fallback import run_agenda_extraction_pipeline


@pytest.mark.parametrize("first_marker,second_marker", [
    ("1A.", "2A."), ("1.A", "2.A"), ("1A.", "2.B"), ("1.", "2A."),
])
def test_a_new_alphanumeric_root_preserves_the_next_business_item(first_marker: str, second_marker: str) -> None:
    agenda_items = run_agenda_extraction_pipeline(
        text=f"{first_marker} Approve contract one\n{second_marker} Approve contract two",
        raw_provider_content=None,
        mode="balanced",
        logger=logging.getLogger(__name__),
    )

    assert [agenda_item["title"] for agenda_item in agenda_items] == ["Approve contract one", "Approve contract two"]


def test_same_root_recommendation_child_remains_nested() -> None:
    agenda_items = run_agenda_extraction_pipeline(
        text=(
            "1. Subject: Regional Transit Agreement\nRecommendation: Take the following action:\n"
            "1A. Authorize the related contract amendment"
        ),
        raw_provider_content=None,
        mode="balanced",
        logger=logging.getLogger(__name__),
    )

    assert [agenda_item["title"] for agenda_item in agenda_items] == ["Subject: Regional Transit Agreement"]


def test_rejected_new_root_does_not_leave_old_parent_context_active() -> None:
    agenda_items = run_agenda_extraction_pipeline(
        text=(
            "1A. Approve contract one\n2A. CALL TO ORDER\n"
            "B. Approve contract two"
        ),
        raw_provider_content=None,
        mode="balanced",
        logger=logging.getLogger(__name__),
    )

    assert [agenda_item["title"] for agenda_item in agenda_items] == ["Approve contract one", "Approve contract two"]

import logging

import pytest

from pipeline.agenda_extraction_fallback import run_agenda_extraction_pipeline


@pytest.mark.parametrize("field", ["Recommendation", "Recommended Action", "From", "Contact", "Vote", "Result", "Action", "Financial Implications"])
def test_body_field_record_mentions_do_not_become_prefix_items(field: str) -> None:
    agenda_items = run_agenda_extraction_pipeline(
        text=(
            "[PAGE 1]\nRegional Transit Agreement Update\n\n"
            f"{field}: Approve agreement 25-03843.\n\n"
            "1. Adopt the annual budget amendment\nRecommendation: Adopt the amendment."
        ),
        raw_provider_content=None,
        mode="balanced",
        logger=logging.getLogger(__name__),
    )

    assert [agenda_item["title"] for agenda_item in agenda_items] == ["Adopt the annual budget amendment"]


@pytest.mark.parametrize("prefix", [
    "25-03843 Regional Transit Agreement Update",
    "Regional Transit Agreement Update 25-03843",
    "Regional Transit Agreement Update\n\n25-03843",
    "Subject: Regional Transit Agreement Update\n\n25-03843",
])
def test_title_record_anchors_remain_eligible_before_numbered_business(prefix: str) -> None:
    agenda_items = run_agenda_extraction_pipeline(
        text=f"[PAGE 1]\n{prefix}\n\n1. Adopt the annual budget amendment\nRecommendation: Adopt it.",
        raw_provider_content=None,
        mode="balanced",
        logger=logging.getLogger(__name__),
    )

    assert any("Regional Transit Agreement Update" in str(agenda_item["title"]) for agenda_item in agenda_items)
    assert any(agenda_item["title"] == "Adopt the annual budget amendment" for agenda_item in agenda_items)

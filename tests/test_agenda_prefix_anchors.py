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


@pytest.mark.parametrize("numbered_suffix", ["", "\n\n1. Adopt the annual budget amendment\nRecommendation: Adopt it."])
@pytest.mark.parametrize("title", [
    "Regional Transit Agreement\nUpdate 25-03843",
    "Regional Transit Agreement 25-03843\nUpdate",
    "Subject: Regional Transit Agreement\nUpdate 25-03843",
    "Subject: Regional Transit Agreement\nUpdate\nRecommendation: Receive the report.\n\n25-03843",
])
def test_record_anchors_and_title_rendering_share_the_complete_title_boundary(title: str, numbered_suffix: str) -> None:
    agenda_items = run_agenda_extraction_pipeline(
        text=f"[PAGE 1]\nCALL TO ORDER\n\nROLL CALL\n\n{title}{numbered_suffix}",
        raw_provider_content=None,
        mode="balanced",
        logger=logging.getLogger(__name__),
    )

    transit = [agenda_item for agenda_item in agenda_items if "Regional Transit Agreement" in str(agenda_item["title"])]
    assert len(transit) == 1
    assert "Update" in str(transit[0]["title"])
    assert "Recommendation" not in str(transit[0]["title"])


@pytest.mark.parametrize("body", [
    "Recommendation: Approve agreement 25-03843.",
    "Recommendation: Approve it.\nSubject: Related agreement 25-03843",
    "Contact: Staff\nRelated agreement 25-03843",
])
def test_body_mentions_cannot_anchor_an_unmarked_prefix_title(body: str) -> None:
    agenda_items = run_agenda_extraction_pipeline(
        text=(f"[PAGE 1]\nCALL TO ORDER\n\nROLL CALL\n\nRegional Transit Agreement\nUpdate\n{body}"
              "\n\n1. Adopt the annual budget amendment"),
        raw_provider_content=None,
        mode="balanced",
        logger=logging.getLogger(__name__),
    )

    assert [agenda_item["title"] for agenda_item in agenda_items] == ["Adopt the annual budget amendment"]


def test_unanchored_paragraph_title_keeps_its_existing_first_line() -> None:
    agenda_items = run_agenda_extraction_pipeline(
        text="[PAGE 1]\nCALL TO ORDER\n\nROLL CALL\n\nRegional Transit Agreement Update\nNotes without a source record ID.",
        raw_provider_content=None,
        mode="balanced",
        logger=logging.getLogger(__name__),
    )

    assert [agenda_item["title"] for agenda_item in agenda_items] == ["Regional Transit Agreement Update"]

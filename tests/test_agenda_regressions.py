import sys
from unittest.mock import MagicMock

# Keep tests lightweight: do not require compiled llama_cpp during unit tests.
sys.modules["llama_cpp"] = MagicMock()
from pipeline.llm import LocalAI


def _extract_with_forced_fallback(text: str):
    """
    Helper: force agenda extraction to use fallback heuristics, not model output.
    """
    LocalAI._instance = None
    ai = LocalAI()
    ai.llm = MagicMock(return_value={"choices": [{"text": "No parseable agenda output"}]})
    return ai.extract_agenda(text)


def test_regression_mixed_page_markers_use_best_available_page_number():
    """
    If OCR emits only one [PAGE N] tag but later inline headers include "Page 2",
    agenda items from that section should map to page 2.
    """
    text = (
        "[PAGE 1]\n\n"
        "Header boilerplate text\n"
        "Thursday, November 6, 2025 ANNOTATED AGENDA Page 2\n"
        "1. Transit Network Update\n"
        "Vote: All Ayes.\n"
    )
    items = _extract_with_forced_fallback(text)

    transit = next((item for item in items if item["title"] == "Transit Network Update"), None)
    assert transit is not None
    assert transit["page_number"] == 2
    assert transit["result"] == "All Ayes."


def test_regression_speaker_list_names_not_promoted_to_agenda_items():
    """
    Speaker-roll sections often use numbered names; these should not become agenda topics.
    """
    text = (
        "[PAGE 1]\n\n"
        "Communications\n"
        "Item #1: Transit Network Update\n"
        "1. Leslie Sakai\n"
        "2. Kirk McCarthy (2)\n"
        "3. Jane and John Doe\n"
        "\n"
        "1. Transit Network Update\n"
    )
    items = _extract_with_forced_fallback(text)
    titles = [item["title"] for item in items]

    assert "Transit Network Update" in titles
    assert "Leslie Sakai" not in titles
    assert "Kirk McCarthy (2)" not in titles
    assert "Jane and John Doe" not in titles


def test_regression_legal_boilerplate_not_promoted_to_agenda_items():
    """
    Legal/notice prose should not appear as agenda rows.
    """
    text = (
        "[PAGE 1]\n\n"
        "I hereby request that the City Clerk provide notice to each member.\n\n"
        "IN WITNESS WHEREOF, I have hereunto set my hand.\n\n"
        "1. Public Employee Appointments\n"
    )
    items = _extract_with_forced_fallback(text)
    titles = [item["title"].lower() for item in items]

    assert "public employee appointments" in titles
    assert all("hereby request" not in title for title in titles)
    assert all("in witness whereof" not in title for title in titles)


def test_regression_accessibility_and_url_boilerplate_not_promoted_to_agenda_items():
    """
    Agenda PDFs often contain participation/accessibility boilerplate plus URLs.
    These should not become agenda item titles.
    """
    text = (
        "[PAGE 1]\n\n"
        "Agendas and agenda reports may be accessed via the Internet at http://example.com\n"
        "COMMUNICATION ACCESS INFORMATION:\n"
        "To request a disability-related accommodation(s) to participate in the meeting...\n"
        "This meeting will be conducted in accordance with the Brown Act, Government Code Section 54953...\n"
        "1. Public Employee Appointments\n"
    )
    items = _extract_with_forced_fallback(text)
    titles = [item["title"].lower() for item in items]

    assert "public employee appointments" in titles
    assert all("agenda reports" not in title for title in titles)
    assert all("communication access information" not in title for title in titles)
    assert all("disability-related" not in title for title in titles)
    assert all("brown act" not in title for title in titles)


def test_regression_on_behalf_of_speaker_lines_not_promoted_to_agenda_items():
    """
    Communications sections can include named speakers like "X, on behalf of Y".
    These lines are people mentions, not agenda items.
    """
    text = (
        "[PAGE 4]\n\n"
        "Communications\n"
        "Item #1: Transit Network Update\n"
        "1. Shona Armstrong, on behalf of Harper & Armstrong, LLP\n"
        "2. Isaiah Stackhouse, on behalf of Trachtenberg Architects\n"
        "1. Transit Network Update\n"
    )
    items = _extract_with_forced_fallback(text)
    titles = [item["title"] for item in items]

    assert "Transit Network Update" in titles
    assert all("on behalf of" not in title.lower() for title in titles)

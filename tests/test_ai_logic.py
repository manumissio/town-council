import pytest
from unittest.mock import MagicMock
import os
import sys

# Keep tests lightweight: do not require compiled llama_cpp during unit tests.
sys.modules["llama_cpp"] = MagicMock()
from pipeline.llm import LocalAI

def test_local_ai_singleton():
    """
    Test: Does the singleton pattern correctly reuse the same instance?
    """
    ai1 = LocalAI()
    ai2 = LocalAI()
    assert ai1 is ai2

def test_local_ai_agenda_extraction():
    """
    Test: Does the extraction logic correctly parse the ITEM format?
    """
    LocalAI._instance = None
    ai = LocalAI()
    mock_llm = MagicMock()
    ai.llm = mock_llm

    # Mock returning the current expected format: ITEM X: Title (Page Y) - Description
    mock_text_response = " Budget Review (Page 3) - Discussion of fiscal year\nITEM 2: Zoning Change (Page 5) - Main Street rezoning"
    mock_llm.return_value = {
        "choices": [
            {"text": mock_text_response}
        ]
    }

    items = ai.extract_agenda("Text content here")

    assert len(items) == 2
    assert items[0]['title'] == "Budget Review"
    assert items[0]['description'] == "Discussion of fiscal year"
    assert items[0]['page_number'] == 3
    assert items[1]['title'] == "Zoning Change"
    assert items[1]['page_number'] == 5

def test_degraded_mode_missing_model(mocker):
    """
    Test: Does the system fail gracefully if the model file is missing?
    """
    LocalAI._instance = None
    mocker.patch('os.path.exists', return_value=False)
    
    ai = LocalAI()
    # We call summarize, which triggers _load_model()
    result = ai.summarize("Some text")
    
    assert result is None
    assert ai.llm is None

def test_local_ai_fallback_logic(mocker):
    """
    Test: Does the system fall back to page-based splitting if AI returns nothing?
    """
    LocalAI._instance = None
    ai = LocalAI()
    mock_llm = MagicMock()
    ai.llm = mock_llm

    # Mock returning nothing to trigger fallback
    mock_llm.return_value = {
        "choices": [
            {"text": ""}
        ]
    }

    # Test text with PAGE markers (the format the fallback expects)
    text = "[PAGE 1]\n\nBudget Review for 2026\nDetailed discussion of the annual budget\n\n[PAGE 2]\n\nZoning Changes\nProposed changes to Main Street zoning"
    items = ai.extract_agenda(text)

    # Fallback should extract items from page markers
    assert len(items) == 2
    assert "Budget Review" in items[0]['title']
    assert "Zoning Changes" in items[1]['title']

def test_local_ai_error_handling():
    """
    Test: Does the system fail gracefully if the AI returns garbage?
    """
    LocalAI._instance = None
    ai = LocalAI()
    mock_llm = MagicMock()
    ai.llm = mock_llm

    # Mock returning garbage that won't match the ITEM pattern
    mock_llm.return_value = {
        "choices": [
            {"text": "Garbage without proper format"}
        ]
    }

    # Should fall back to page-based splitting when AI output doesn't parse
    text = "[PAGE 1]\n\nAnnual Budget Proposal\nDiscussion of revenue and expenses for the upcoming fiscal year"
    items = ai.extract_agenda(text)
    assert len(items) >= 1
    assert "Budget" in items[0]['title'] or "Annual" in items[0]['title']


def test_local_ai_fallback_filters_header_noise():
    """
    Regression: fallback should ignore meeting headers and spaced-letter OCR noise.
    """
    LocalAI._instance = None
    ai = LocalAI()
    mock_llm = MagicMock()
    ai.llm = mock_llm

    # Force fallback path by returning non-parseable AI output.
    mock_llm.return_value = {
        "choices": [
            {"text": "No parseable agenda output"}
        ]
    }

    text = (
        "[PAGE 1]\n\n"
        "Special Closed Meeting 10/03/11\n\n"
        "P R O C L A M A T I O N\n\n"
        "1. Budget Amendment\n"
        "Approve revised budget allocations for FY 2026\n"
    )
    items = ai.extract_agenda(text)

    assert len(items) == 1
    assert "budget amendment" in items[0]["title"].lower()


def test_local_ai_fallback_uses_inline_page_headers_and_skips_speaker_lists():
    """
    Regression: if OCR only has [PAGE 1], fallback should still detect later "Page N" headers.
    Also ensure numbered speaker lists under Communications do not become agenda items.
    """
    LocalAI._instance = None
    ai = LocalAI()
    mock_llm = MagicMock()
    ai.llm = mock_llm
    mock_llm.return_value = {"choices": [{"text": "No parseable agenda output"}]}

    text = (
        "[PAGE 1]\n\n"
        "Thursday, November 6, 2025 ANNOTATED AGENDA Page 2\n"
        "1. Corridors Zoning Update\n"
        "Vote: All Ayes.\n"
        "2. San Pablo Avenue Specific Plan\n"
        "Vote: All Ayes.\n"
        "\nCommunications\n"
        "Item #1: Corridors Zoning Update\n"
        "Item #2: San Pablo Avenue Specific Plan\n"
        "1. Leslie Sakai\n"
        "2. Kirk McCarthy (2)\n"
    )
    items = ai.extract_agenda(text)
    titles = [item["title"] for item in items]

    assert "Corridors Zoning Update" in titles
    assert "San Pablo Avenue Specific Plan" in titles
    assert "Leslie Sakai" not in titles
    assert "Kirk McCarthy (2)" not in titles
    for item in items:
        assert item["page_number"] == 2


def test_local_ai_fallback_extracts_vote_result_from_item_block():
    """
    Regression: fallback should carry vote outcomes into result so the UI can display them.
    """
    LocalAI._instance = None
    ai = LocalAI()
    mock_llm = MagicMock()
    ai.llm = mock_llm
    mock_llm.return_value = {"choices": [{"text": "No parseable agenda output"}]}

    text = (
        "[PAGE 1]\n\n"
        "1. Budget Hearing\n"
        "Action: M/S/C to approve recommendation.\n"
        "Vote: All Ayes.\n"
    )
    items = ai.extract_agenda(text)

    assert len(items) == 1
    assert items[0]["title"] == "Budget Hearing"
    assert items[0]["result"] == "All Ayes."


def test_local_ai_fallback_skips_person_heavy_numbered_lists_without_keyword():
    """
    Regression: some pages contain numbered speaker lists without "Communications" label.
    If the block is mostly names, those lines should be excluded.
    """
    LocalAI._instance = None
    ai = LocalAI()
    mock_llm = MagicMock()
    ai.llm = mock_llm
    mock_llm.return_value = {"choices": [{"text": "No parseable agenda output"}]}

    text = (
        "[PAGE 1]\n\n"
        "1. Corridors Zoning Update\n"
        "2. San Pablo Avenue Specific Plan\n"
        "[PAGE 2]\n\n"
        "1. Leslie Sakai\n"
        "2. Kirk McCarthy (2)\n"
        "3. Preet Dhillon\n"
        "4. Doris Fulder Nassiry (3)\n"
        "5. Susan Jones\n"
        "6. Barbara Gilbert (2)\n"
    )
    items = ai.extract_agenda(text)
    titles = [item["title"] for item in items]

    assert "Corridors Zoning Update" in titles
    assert "San Pablo Avenue Specific Plan" in titles
    assert "Leslie Sakai" not in titles
    assert "Susan Jones" not in titles


def test_local_ai_fallback_filters_metadata_headers():
    """
    Regression: date/location/official header lines should not become agenda items.
    """
    LocalAI._instance = None
    ai = LocalAI()
    mock_llm = MagicMock()
    ai.llm = mock_llm
    mock_llm.return_value = {"choices": [{"text": "No parseable agenda output"}]}

    text = (
        "[PAGE 1]\n\n"
        "Thursday, November 6, 2025\n"
        "1231 Addison Street, Berkeley, CA\n"
        "ADENA ISHII, MAYOR\n"
        "1. Budget Hearing\n"
    )
    items = ai.extract_agenda(text)
    titles = [item["title"] for item in items]

    assert "Budget Hearing" in titles
    assert "Thursday, November 6, 2025" not in titles
    assert "ADENA ISHII, MAYOR" not in titles


def test_local_ai_paragraph_fallback_skips_name_lines_in_communications_pages():
    """
    Regression: paragraph mode should not treat public speaker names as agenda items.
    """
    LocalAI._instance = None
    ai = LocalAI()
    mock_llm = MagicMock()
    ai.llm = mock_llm
    mock_llm.return_value = {"choices": [{"text": "No parseable agenda output"}]}

    text = (
        "[PAGE 1]\n\n"
        "Communications\n\n"
        "Leslie Sakai\nPublic comment regarding Item 1.\n\n"
        "Kirk McCarthy (2)\nPublic comment regarding Item 2.\n\n"
        "1. Corridors Zoning Update\n"
    )
    items = ai.extract_agenda(text)
    titles = [item["title"] for item in items]

    assert "Corridors Zoning Update" in titles
    assert "Leslie Sakai" not in titles
    assert "Kirk McCarthy (2)" not in titles

import pytest
from unittest.mock import MagicMock
import os
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
    Test: Does the extraction logic correctly parse bulleted text?
    """
    LocalAI._instance = None
    ai = LocalAI()
    mock_llm = MagicMock()
    ai.llm = mock_llm

    # Mock returning bulleted text (the new format)
    mock_text_response = "* Item 1 - Budget discussion\n* Item 2 - Zoning"
    mock_llm.return_value = {
        "choices": [
            {"text": mock_text_response}
        ]
    }

    items = ai.extract_agenda("Text content here")

    assert len(items) == 2
    assert items[0]['title'] == "Item 1"
    assert items[0]['description'] == "Budget discussion"
    assert items[1]['title'] == "Item 2"

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
    Test: Does the system fall back to paragraph splitting if AI returns nothing?
    """
    LocalAI._instance = None
    ai = LocalAI()
    mock_llm = MagicMock()
    ai.llm = mock_llm

    # Mock returning nothing
    mock_llm.return_value = {
        "choices": [
            {"text": ""}
        ]
    }

    # Test text with clear paragraphs
    text = "First paragraph that is long enough to be an item.\n\nSecond paragraph that is also long enough."
    items = ai.extract_agenda(text)

    # Fallback should split by \n\n
    assert len(items) == 2
    assert "First paragraph" in items[0]['title']

def test_local_ai_error_handling():
    """
    Test: Does the system fail gracefully if the AI returns garbage?
    """
    LocalAI._instance = None
    ai = LocalAI()
    mock_llm = MagicMock()
    ai.llm = mock_llm

    mock_llm.return_value = {
        "choices": [
            {"text": "Garbage without bullets"}
        ]
    }

    # Should fall back to paragraph splitting
    items = ai.extract_agenda("Paragraph 1. Paragraph 1. Paragraph 1.\n\nParagraph 2. Paragraph 2.")
    assert len(items) >= 1
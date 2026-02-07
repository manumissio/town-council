import pytest
import os
from unittest.mock import MagicMock
import sys

# Mock llama_cpp module
sys.modules["llama_cpp"] = MagicMock()

from pipeline.llm import LocalAI

def test_local_ai_summarize():
    """
    Test: Does the LocalAI class correctly call the internal llama model?
    """
    LocalAI._instance = None
    ai = LocalAI()
    # Direct injection for isolated testing
    mock_llm = MagicMock()
    ai.llm = mock_llm
    
    mock_llm.return_value = {
        "choices": [
            {"text": "- Point 1\n- Point 2\n- Point 3"}
        ]
    }

    summary = ai.summarize("Zoning text")

    assert "- Point 1" in summary
    assert mock_llm.called
    mock_llm.reset.assert_called_once()

def test_local_ai_agenda_extraction():
    """
    Test: Does the extraction logic correctly parse JSON?
    """
    LocalAI._instance = None
    ai = LocalAI()
    mock_llm = MagicMock()
    ai.llm = mock_llm
    
    # Mock returning a JSON object with 'items' key (new robust format)
    mock_json_response = '{"items": [{"title": "Item 1", "description": "Budget"}]}'
    mock_llm.return_value = {
        "choices": [
            {"text": mock_json_response}
        ]
    }

    items = ai.extract_agenda("Text")

    assert len(items) == 1
    assert items[0]['title'] == "Item 1"
    mock_llm.reset.assert_called_once()

def test_degraded_mode_missing_model(mocker):
    """
    Test: Does the system fail gracefully if the model file is missing?
    """
    LocalAI._instance = None
    mocker.patch('os.path.exists', return_value=False)
    
    ai = LocalAI()
    # We call summarize, which triggers _load_model()
    result = ai.summarize("Some text")
    
    assert "Summarization unavailable" in result
    assert ai.llm is None

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
            {"text": "This is not JSON"}
        ]
    }

    items = ai.extract_agenda("Text")

    assert items == []
    mock_llm.reset.assert_called()

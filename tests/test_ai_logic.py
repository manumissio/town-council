import pytest
from unittest.mock import MagicMock
import sys

# Mock llama_cpp BEFORE importing LocalAI to avoid loading the real model
sys.modules["llama_cpp"] = MagicMock()

from pipeline.llm import LocalAI

def test_local_ai_summarize(mocker):
    """
    Test: Does the LocalAI class correctly call the llama model?
    """
    # 1. Reset Singleton
    LocalAI._instance = None
    
    # 2. Setup Mock
    # We mock the CLASS so that Llama(...) returns our mock instance
    mock_llm_class = mocker.patch('pipeline.llm.Llama')
    mock_llm_instance = mock_llm_class.return_value
    
    # Configure the instance method to return a REAL DICTIONARY
    mock_llm_instance.create_chat_completion.return_value = {
        "choices": [
            {"message": {"content": "- Point 1\n- Point 2\n- Point 3"}}
        ]
    }
    
    # Mock file existence
    mocker.patch('os.path.exists', return_value=True)

    # 3. Action
    ai = LocalAI()
    summary = ai.summarize("This is a long meeting text about zoning.")

    # 4. Verify
    assert "- Point 1" in summary
    
    # Verify strict limits
    call_args = mock_llm_instance.create_chat_completion.call_args
    assert call_args[1]['max_tokens'] == 256
    
    # Verify memory reset
    mock_llm_instance.reset.assert_called_once()

def test_local_ai_agenda_extraction(mocker):
    """
    Test: Does the extraction logic correctly parse JSON?
    """
    LocalAI._instance = None
    
    mock_llm_class = mocker.patch('pipeline.llm.Llama')
    mock_llm_instance = mock_llm_class.return_value
    
    # Return a valid JSON string
    mock_json_response = '[{"title": "Item 1", "description": "Discuss budget"}]'
    mock_llm_instance.create_chat_completion.return_value = {
        "choices": [
            {"message": {"content": mock_json_response}}
        ]
    }
    
    mocker.patch('os.path.exists', return_value=True)

    # Action
    ai = LocalAI()
    items = ai.extract_agenda("Meeting text here.")

    # Verify
    assert len(items) == 1
    assert items[0]['title'] == "Item 1"
    
    # Verify JSON mode
    call_args = mock_llm_instance.create_chat_completion.call_args
    assert call_args[1]['response_format'] == {"type": "json_object"}

def test_local_ai_error_handling(mocker):
    """
    Test: Does the system fail gracefully if the AI returns garbage?
    """
    LocalAI._instance = None
    
    mock_llm_class = mocker.patch('pipeline.llm.Llama')
    mock_llm_instance = mock_llm_class.return_value
    
    # Return bad JSON
    mock_llm_instance.create_chat_completion.return_value = {
        "choices": [
            {"message": {"content": "This is not JSON"}}
        ]
    }
    
    mocker.patch('os.path.exists', return_value=True)

    # Action
    ai = LocalAI()
    items = ai.extract_agenda("Text")

    # Verify
    assert items == []
    # Ensure we still reset memory even after an error
    mock_llm_instance.reset.assert_called()

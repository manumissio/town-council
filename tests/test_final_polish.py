import pytest
from unittest.mock import MagicMock
import sys
import os

from pipeline.llm import LocalAI

def test_local_ai_missing_model_returns_none(mocker):
    """
    Test: Does summarize() return None (not a string) when model is missing?
    """
    # Force fresh instance
    LocalAI._instance = None
    ai = LocalAI()
    
    # Mock load_model to do nothing (leaving self.llm as None)
    mocker.patch('os.path.exists', return_value=False)
    
    result = ai.summarize("test")
    assert result is None

def test_ai_prompt_schema():
    """
    Test: Does the prompt ask for structured agenda items with page numbers?
    """
    LocalAI._instance = None
    ai = LocalAI()

    mock_llm = MagicMock()
    mock_llm.return_value = {"choices": [{"text": " Budget (Page 1) - Desc"}]}
    ai.llm = mock_llm

    ai.extract_agenda("meeting text")

    # Check the call arguments
    args, _ = mock_llm.call_args
    prompt_text = args[0]

    # Verify prompt asks for agenda items with page numbers and specific format
    assert "agenda items" in prompt_text.lower()
    assert "page" in prompt_text.lower()
    assert "ITEM" in prompt_text  # The format shows ITEM as an example
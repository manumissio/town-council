import pytest
from unittest.mock import MagicMock
import sys
import os

# Setup mocks
sys.modules["llama_cpp"] = MagicMock()
sys.modules["redis"] = MagicMock()

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
    Test: Does the prompt ask for the new schema fields?
    """
    LocalAI._instance = None
    ai = LocalAI()
    
    # We inspect the code or mock the LLM call to see the prompt
    # Since we can't easily inspect the local variable 'prompt' inside the method,
    # we will mock self.llm and check the arguments passed to it.
    
    mock_llm = MagicMock()
    mock_llm.return_value = {"choices": [{"text": "{}"}]} # Prevent crash on json load
    ai.llm = mock_llm
    
    # Correct mocking approach
    # We patch os.path.exists globally for this test
    # Actually, if we set ai.llm manually, _load_model returns early.
    
    ai.extract_agenda("meeting text")
    
    # Check the call arguments
    args, _ = mock_llm.call_args
    prompt_text = args[0]
    
    assert "classification" in prompt_text
    assert "result" in prompt_text
    assert "Action" in prompt_text

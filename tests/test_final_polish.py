import pytest
from unittest.mock import MagicMock
import sys
import os

from pipeline.llm import HttpInferenceProvider, LocalAI

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
    captured_prompt: dict[str, str] = {}

    def fake_extract_agenda(self, prompt: str, **_: object) -> str:
        captured_prompt["prompt"] = prompt
        return "ITEM: Budget (Page 1) - Desc"

    original_backend = sys.modules["pipeline.llm"].LOCAL_AI_BACKEND
    sys.modules["pipeline.llm"].LOCAL_AI_BACKEND = "http"
    original_provider = HttpInferenceProvider.extract_agenda
    HttpInferenceProvider.extract_agenda = fake_extract_agenda

    try:
        ai.extract_agenda("meeting text")
    finally:
        HttpInferenceProvider.extract_agenda = original_provider
        sys.modules["pipeline.llm"].LOCAL_AI_BACKEND = original_backend
        LocalAI._instance = None

    prompt_text = captured_prompt["prompt"]

    # Verify prompt asks for agenda items with page numbers and specific format
    assert "agenda items" in prompt_text.lower()
    assert "page" in prompt_text.lower()
    assert "ITEM" in prompt_text  # The format shows ITEM as an example

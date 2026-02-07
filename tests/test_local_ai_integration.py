import pytest
import os
from unittest.mock import MagicMock
import sys

# Mock llama_cpp to avoid loading C++ libraries during CI tests
# We must mock it BEFORE importing LocalAI
sys.modules["llama_cpp"] = MagicMock()

from pipeline.llm import LocalAI

def test_model_path_configuration(mocker):
    """
    Test: Does the LocalAI class look for the model in the correct 'baked' location?
    """
    # 1. Reset Singleton (Crucial for tests!)
    LocalAI._instance = None
    
    # 2. Mock Llama CLASS (not instance)
    # When code calls Llama(...), it gets mock_instance
    mock_class = mocker.patch('pipeline.llm.Llama')
    
    # 3. Mock file existence
    mocker.patch('os.path.exists', return_value=True)
    
    # 4. Initialize
    ai = LocalAI()
    
    # 5. Verify the path passed to the CONSTRUCTOR
    mock_class.assert_called_once()
    call_kwargs = mock_class.call_args[1]
    
    assert call_kwargs['model_path'] == "/models/gemma-3-270m-it-Q4_K_M.gguf"
    assert call_kwargs['n_ctx'] == 8192
    assert call_kwargs['n_gpu_layers'] == 0 # CPU Only

def test_singleton_pattern(mocker):
    """
    Test: Does the Singleton ensure we only load the heavy model once?
    """
    # 1. Reset Singleton
    LocalAI._instance = None
    
    mocker.patch('os.path.exists', return_value=True)
    mock_class = mocker.patch('pipeline.llm.Llama')
    
    # First instantiation
    ai1 = LocalAI()
    # Second instantiation
    ai2 = LocalAI()
    
    assert ai1 is ai2
    # The Llama constructor should have been called exactly ONCE
    mock_class.assert_called_once()
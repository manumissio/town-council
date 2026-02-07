import pytest
import sys
from unittest.mock import MagicMock

@pytest.fixture(autouse=True)
def reset_singleton():
    """
    Reset the LocalAI singleton before every test.
    """
    # 1. Ensure llama_cpp is mocked so re-imports don't crash
    if "llama_cpp" not in sys.modules:
        sys.modules["llama_cpp"] = MagicMock()
        
    # 2. Reset the singleton instance if it exists
    if "pipeline.llm" in sys.modules:
        try:
            from pipeline.llm import LocalAI
            LocalAI._instance = None
        except Exception:
            pass
    yield

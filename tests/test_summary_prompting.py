import sys
from unittest.mock import MagicMock

# The unit tests here only validate prompt/text preparation logic.
# Mock the heavy llama-cpp binding so importing pipeline.llm doesn't require native deps.
sys.modules["llama_cpp"] = MagicMock()


def test_prepare_summary_prompt_uses_agenda_language():
    from pipeline.llm import prepare_summary_prompt

    prompt = prepare_summary_prompt("Agenda item 1: Housing", doc_kind="agenda")
    assert "agenda" in prompt.lower()
    assert "minutes" not in prompt.lower()


def test_prepare_summary_prompt_uses_minutes_language():
    from pipeline.llm import prepare_summary_prompt

    prompt = prepare_summary_prompt("Motion approved. Vote: All Ayes.", doc_kind="minutes")
    assert "minutes" in prompt.lower()


def test_strip_summary_boilerplate_removes_urls_and_zoom_words():
    from pipeline.llm import _strip_summary_boilerplate

    raw = """
    OPTIONS TO OBSERVE:
    Watch a live stream online at https://example.com/webcast
    Join Zoom Webinar ID 123

    Item 1. Approve the budget.
    """
    cleaned = _strip_summary_boilerplate(raw)
    assert "http" not in cleaned.lower()
    assert "zoom" not in cleaned.lower()
    assert "Approve the budget" in cleaned

import sys
from unittest.mock import MagicMock

sys.modules["llama_cpp"] = MagicMock()

from pipeline.agenda_summary_inputs import build_agenda_summary_input_bundle


def test_agenda_summary_input_applies_payload_budget_and_truncation_meta():
    catalog = MagicMock()
    catalog.content = "Long enough agenda content to pass quality gates for this test case."
    document = MagicMock(category="agenda")

    long_desc = "x" * 800
    agenda_items = [
        MagicMock(title=f"Item {i}", description=long_desc, classification="Agenda Item", result="", page_number=i)
        for i in range(1, 25)
    ]

    summary_input = build_agenda_summary_input_bundle(
        catalog=catalog,
        document=document,
        agenda_items=agenda_items,
        max_input_chars=1200,
        min_reserved_output_chars=200,
    )

    assert summary_input["status"] == "ready"
    trunc = summary_input["truncation_meta"]
    assert trunc["items_included"] < trunc["items_total"]
    assert trunc["items_truncated"] > 0
    assert trunc["input_chars"] <= 1000

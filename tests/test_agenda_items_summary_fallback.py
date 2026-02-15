from pipeline.llm import _agenda_items_summary_is_too_short, _deterministic_agenda_items_summary


def test_agenda_items_summary_is_too_short_flags_empty_and_tiny():
    assert _agenda_items_summary_is_too_short("") is True
    assert _agenda_items_summary_is_too_short("BLUF: Hi.") is True


def test_agenda_items_summary_is_too_short_accepts_reasonable_output():
    text = (
        "BLUF: Agenda includes key land use and budget items.\n"
        "This meeting is scheduled to consider multiple proposals and updates.\n"
        "- Corridors Zoning Update\n"
        "- San Pablo Avenue Specific Plan\n"
        "- Budget Amendment\n"
    )
    assert _agenda_items_summary_is_too_short(text) is False


def test_deterministic_agenda_items_summary_includes_all_items_up_to_cap():
    items = [f"Item {i}" for i in range(1, 31)]
    out = _deterministic_agenda_items_summary(items, max_bullets=25)
    assert out.startswith("BLUF:")
    assert "Agenda includes 30 substantive items" in out
    assert "- Item 1" in out
    assert "- Item 25" in out
    assert "- Item 26" not in out
    assert "(+5 more)" in out


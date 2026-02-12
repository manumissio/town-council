from pipeline.summary_quality import (
    analyze_source_text,
    is_source_summarizable,
    is_source_topicable,
    build_low_signal_message,
)


def test_analyze_source_text_flags_short_low_signal_input():
    quality = analyze_source_text("Agenda")
    assert quality.char_count < 120
    assert not is_source_summarizable(quality)
    assert not is_source_topicable(quality)
    assert "Not enough extracted text" in build_low_signal_message(quality)


def test_analyze_source_text_accepts_rich_meeting_content():
    text = """
    CITY COUNCIL REGULAR MEETING
    Call to order and roll call.
    Item 1. Approve revised budget allocations for transportation.
    Motion: Adopted.
    Vote: All Ayes.
    Item 2. Authorize contract amendment for road resurfacing.
    Public comment received from three speakers.
    """
    quality = analyze_source_text(text)
    assert quality.char_count >= 120
    assert quality.distinct_token_count >= 18
    assert is_source_summarizable(quality)
    assert is_source_topicable(quality)

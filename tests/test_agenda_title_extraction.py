def test_extract_agenda_titles_skips_attendance_boilerplate_and_matches_numbered_items():
    from pipeline.tasks import _extract_agenda_titles_from_text

    text = """
    [PAGE 1]
    TELECONFERENCE / PUBLIC PARTICIPATION INFORMATION
    1. Email comments by 5:00 p.m. to clerk@example.com
    2. Join the webinar using your browser

    ORDER OF BUSINESS
    1. Budget Amendment Vote: All Ayes.
    2. Housing Element Update
    """

    titles = _extract_agenda_titles_from_text(text, max_titles=3)
    assert titles == ["Budget Amendment Vote: All Ayes.", "Housing Element Update"]


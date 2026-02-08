from pipeline.agenda_qa import QAThresholds, needs_regeneration, score_agenda_items


def test_qa_flags_boilerplate_heavy_titles():
    items = [
        {"title": "COMMUNICATION ACCESS INFORMATION:", "page_number": 1, "result": ""},
        {"title": "Agendas and agenda reports may be accessed via the Internet at http://example.com", "page_number": 1, "result": ""},
        {"title": "Public Employee Appointments", "page_number": 2, "result": ""},
    ]
    res = score_agenda_items(items, catalog_text="")
    assert "high_boilerplate_rate" in res.flags
    assert needs_regeneration(res, thresholds=QAThresholds(suspect_severity=1)) is True


def test_qa_flags_name_like_titles_from_speaker_rolls():
    items = [
        {"title": "Leslie Sakai", "page_number": 1, "result": ""},
        {"title": "Kirk McCarthy (2)", "page_number": 1, "result": ""},
        {"title": "Transit Network Update", "page_number": 2, "result": ""},
    ]
    res = score_agenda_items(items, catalog_text="")
    assert "high_name_like_rate" in res.flags
    assert needs_regeneration(res, thresholds=QAThresholds(suspect_severity=1)) is True


def test_qa_flags_page_numbers_suspect_when_raw_has_page_2():
    items = [
        {"title": "Budget Amendment", "page_number": 1, "result": ""},
        {"title": "Public Employee Appointment", "page_number": 1, "result": ""},
        {"title": "Adjournment", "page_number": 1, "result": ""},
    ]
    text = "[PAGE 1]\n...\nThursday, Nov 6, 2025 ANNOTATED AGENDA Page 2\n1. Budget Amendment\n"
    res = score_agenda_items(items, catalog_text=text)
    assert "page_numbers_suspect" in res.flags


def test_qa_flags_votes_missed_when_raw_contains_vote_lines():
    items = [
        {"title": "Budget Amendment", "page_number": 2, "result": ""},
        {"title": "Transit Network Update", "page_number": 3, "result": ""},
    ]
    text = "Action: Something\nVote: All Ayes.\n"
    res = score_agenda_items(items, catalog_text=text)
    assert "votes_missed" in res.flags


def test_qa_clean_set_not_flagged():
    items = [
        {"title": "Budget Amendment", "page_number": 3, "result": "All Ayes."},
        {"title": "Transit Network Update", "page_number": 4, "result": ""},
    ]
    text = "[PAGE 3]\n1. Budget Amendment\nVote: All Ayes.\n[PAGE 4]\n2. Transit Network Update\n"
    res = score_agenda_items(items, catalog_text=text)
    assert res.flags == []
    assert needs_regeneration(res) is False


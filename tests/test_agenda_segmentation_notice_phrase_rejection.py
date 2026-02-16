def test_extract_agenda_rejects_expanded_notice_phrase_family():
    from pipeline.llm import LocalAI

    text = """
    [PAGE 4]
    21. described in the notice or agenda for this meeting, before or during consideration of that item.
    22. request card located in front of the Commission, and deliver it to City Staff prior to discussion of the item.
    23. when you are called, proceed to the podium and the Chair will recognize you.
    24. address the Planning Commission on any other item not on the agenda.
    25. comments to three (3) minutes or less.

    [PAGE 5]
    1. Subject: Annual Housing Element Progress Report
    Recommended Action: Receive and file the annual report.
    """

    items = LocalAI().extract_agenda(text)
    titles = [it.get("title", "").lower() for it in items]
    joined = " ".join(titles)
    assert "described in the notice" not in joined
    assert "consideration of that item" not in joined
    assert "request card located in front" not in joined
    assert "prior to discussion of the" not in joined
    assert "proceed to the podium" not in joined
    assert "address the planning commission" not in joined
    assert "comments to three" not in joined
    assert any("annual housing element progress report" in t for t in titles)

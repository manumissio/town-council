def test_extract_agenda_filters_cupertino_public_notice_block():
    from pipeline.llm import LocalAI

    text = """
    [PAGE 4]
    18. meeting agendas and writings distributed for the meeting that are public records will be made available
    19. in the appropriate alternative format.
    20. Any writings or documents provided to a majority of the Planning Commission after publication of the
    21. IMPORTANT NOTICE: Please be advised that pursuant to Cupertino Municipal Code section
    22. concerning a matter on the agenda are included as supplemental material to the agendized item. These
    23. be made publicly available on the City website.
    24. described in the notice or agenda for this meeting, before or during consideration of that item. If you
    25. wish to address the Planning Commission on any issue that is on this agenda, please complete a speaker
    26. request card located in front of the Commission, and deliver it to the City Staff prior to discussion of the
    27. item. When you are called, proceed to the podium and the Chair will recognize you. If you wish to
    28. address the Planning Commission on any other item not on the agenda, you may do so by during the
    29. comments to three (3) minutes or less.

    [PAGE 5]
    1. Subject: Study Session on Housing Element Program
    Recommended Action: Receive report and provide direction.
    """

    items = LocalAI().extract_agenda(text)
    titles = [it.get("title", "").lower() for it in items]
    joined = " ".join(titles)
    assert "important notice" not in joined
    assert "speaker request card" not in joined
    assert "agendized item" not in joined
    assert "in the appropriate alternative format" not in joined
    assert "comments to three" not in joined
    assert any("study session on housing element program" in t for t in titles)

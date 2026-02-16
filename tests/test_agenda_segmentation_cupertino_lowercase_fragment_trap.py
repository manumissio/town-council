def test_extract_agenda_rejects_numbered_lowercase_fragments_but_keeps_substantive_lines():
    from pipeline.llm import LocalAI

    text = """
    [PAGE 4]
    16. in the appropriate alternative format.
    17. described in the notice or agenda for this meeting.
    18. request card located in front of the Commission.
    19. Approve the Zoning Map Amendment (Z-2018-02).
    """

    items = LocalAI().extract_agenda(text)
    titles = [it.get("title", "").lower() for it in items]
    joined = " ".join(titles)
    assert "in the appropriate alternative format" not in joined
    assert "described in the notice" not in joined
    assert "request card located in front" not in joined
    assert any("approve the zoning map amendment" in t for t in titles)


def test_extract_agenda_rejects_non_alpha_numbered_lines():
    from pipeline.llm import LocalAI

    text = """
    [PAGE 2]
    1. ---
    2. 12.
    3. Subject: Capital Improvement Program Update
    Recommended Action: Receive report and provide direction.
    """

    items = LocalAI().extract_agenda(text)
    titles = [it.get("title", "").lower() for it in items]
    assert all("---" not in t for t in titles)
    assert all(t != "12." for t in titles)
    assert any("capital improvement program update" in t for t in titles)

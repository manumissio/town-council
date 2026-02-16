def test_extract_agenda_rejects_contact_and_letterhead_noise():
    from pipeline.llm import LocalAI

    text = """
    [PAGE 1]
    1. Milvia Street, Berkeley, CA 94704 Tel: (510) 981-7000 Fax: (510) 981-7099
    2. From: Paul Buddenhagen, City Manager
    3. Office of the City Manager
    4. Subject: Housing Element Update
    Recommended Action: Receive an informational update.
    """

    items = LocalAI().extract_agenda(text)
    titles = [it.get("title", "").lower() for it in items]
    joined = " ".join(titles)
    assert "milvia street" not in joined
    assert "from: paul buddenhagen" not in joined
    assert "office of the city manager" not in joined
    assert any("housing element update" in t for t in titles)

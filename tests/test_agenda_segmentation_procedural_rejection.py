def test_extract_agenda_rejects_procedural_placeholders():
    from pipeline.llm import LocalAI

    text = """
    [PAGE 1]
    1. Call to Order
    2. Roll Call
    3. Public Comment
    4. Approval of Minutes

    [PAGE 2]
    1. Subject: Zoning Ordinance Amendment
    Recommended Action: Introduce and adopt the zoning ordinance amendment.
    """

    items = LocalAI().extract_agenda(text)
    titles = [it.get("title", "").lower() for it in items]
    joined = " ".join(titles)
    assert "call to order" not in joined
    assert "roll call" not in joined
    assert "public comment" not in joined
    assert "approval of minutes" not in joined
    assert any("zoning ordinance amendment" in t for t in titles)

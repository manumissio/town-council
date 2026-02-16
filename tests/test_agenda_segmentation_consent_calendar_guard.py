def test_extract_agenda_rejects_approval_of_minutes_but_keeps_substantive_approval():
    from pipeline.llm import LocalAI

    text = """
    [PAGE 1]
    1. Approval of Minutes
    2. Approval of Contract for Street Sweeping Services
    Recommended Action: Authorize the City Manager to execute the contract.
    """

    items = LocalAI().extract_agenda(text)
    titles = [it.get("title", "").lower() for it in items]
    assert all("approval of minutes" not in t for t in titles)
    assert any("approval of contract for street sweeping services" in t for t in titles)

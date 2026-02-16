def test_extract_agenda_dedupes_toc_and_prefers_body_page():
    from pipeline.llm import LocalAI

    text = """
    [PAGE 1]
    1. Subject: Budget Amendment

    [PAGE 4]
    1. Subject: Budget Amendment
    Recommended Action: Adopt resolution approving the budget amendment.
    """

    items = LocalAI().extract_agenda(text)
    budget_items = [it for it in items if "budget amendment" in it.get("title", "").lower()]
    assert len(budget_items) == 1
    assert budget_items[0].get("page_number") == 4

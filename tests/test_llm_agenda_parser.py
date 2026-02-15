from pipeline.llm import parse_llm_agenda_items


def test_parse_llm_agenda_items_preserves_multiline_descriptions_and_separator_variants():
    text = (
        "ITEM 1: First Item (Page 2) - First line of desc\n"
        "continued line of desc\n"
        "ITEM 2: Second Item (Page 3) : Colon separator desc\n"
        "ITEM 3: Third Item (Page 4) \u2013 En-dash desc\n"
        "ITEM 4: Fourth Item (Page 5) \u2014 Em-dash desc\n"
        "ITEM 5: Fifth Item (Page 6) desc with no separator\n"
    )
    items = parse_llm_agenda_items(text)
    assert [it["order"] for it in items] == [1, 2, 3, 4, 5]
    assert items[0]["page_number"] == 2
    assert items[0]["title"] == "First Item"
    assert items[0]["description"] == "First line of desc continued line of desc"
    assert items[1]["description"] == "Colon separator desc"
    assert items[2]["description"] == "En-dash desc"
    assert items[3]["description"] == "Em-dash desc"
    assert items[4]["description"] == "desc with no separator"


def test_parse_llm_agenda_items_defaults_missing_page_to_one():
    text = "ITEM 7: No Page Provided - Something happened"
    items = parse_llm_agenda_items(text)
    assert len(items) == 1
    assert items[0]["order"] == 7
    assert items[0]["page_number"] == 1

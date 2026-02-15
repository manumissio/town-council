def test_extract_agenda_skips_teleconference_covid_ada_numbered_boilerplate():
    """
    Regression: numbered participation boilerplate should not become agenda items.
    """
    from pipeline.llm import LocalAI

    text = """
    [PAGE 1]
    TELECONFERENCE / PUBLIC PARTICIPATION INFORMATION TO HELP STOP THE SPREAD OF COVID-19
    1. Join the webinar using your internet browser (Chrome/Firefox/Edge).
    2. To make a public comment, click 'raise hand' and unmute when called.
    3. For disability-related accommodations (ADA), contact the City Clerk.
    4. E-mail comments by 5:00 p.m. to clerk@example.com
    5. 162.255.37.11 (US West)
    6. 144.110 (Amsterdam Netherlands)
    7. 140.110 (Germany
    8. Please read the following instructions carefully:
    9. You will be asked to enter an email address and a name, followed by a confirmation email. Your email address will not be disclosed.
    10. When asked for a name, you may enter "Cupertino Resident" or similar designation.
    11. Speakers will be notified shortly before they are called to speak.
    12. When called, please limit your remarks to the time allotted and the specific agenda item.

    [PAGE 2]
    ROLL CALL
    WRITTEN COMMUNICATIONS
    OLD BUSINESS
    2. Subject: Future Agenda Items (Eschelbeck)
    Recommended Action: Develop and maintain a list of future agenda items.
    3. Subject: Crash Data Analysis (Ganga)
    Recommended Action: Receive report on crash data between 2010 and 2014.
    """

    local_ai = LocalAI()
    items = local_ai.extract_agenda(text)
    titles = [it.get("title", "") for it in items]
    lowered = " ".join(titles).lower()

    assert any("future agenda items" in t.lower() for t in titles)
    assert any("crash data analysis" in t.lower() for t in titles)
    assert "teleconference" not in lowered
    assert "public participation" not in lowered
    assert "covid" not in lowered
    assert "ada" not in lowered
    assert "e-mail comments" not in lowered
    assert "us west" not in lowered
    assert "amsterdam" not in lowered
    assert "germany" not in lowered
    assert "instructions carefully" not in lowered
    assert "email address" not in lowered
    assert "will not be disclosed" not in lowered
    assert "designation" not in lowered
    assert "called to speak" not in lowered
    assert "limit your remarks" not in lowered
    assert "time allotted" not in lowered
    assert len(items) >= 2

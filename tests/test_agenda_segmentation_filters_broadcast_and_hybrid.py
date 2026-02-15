def test_extract_agenda_filters_hybrid_and_broadcast_boilerplate():
    """
    Regression: hybrid-attendance blurbs and broadcast availability notices
    should not become agenda items.
    """
    from pipeline.llm import LocalAI

    text = """
    [PAGE 1]
    1. This meeting will be conducted in a hybrid model with both in-person and virtual attendance. Attend this meeting remotely using Zoom.
    2. Live captioned broadcasts of Council meetings are available on B-TV (Channel 33) and via internet video stream.
    3. Public Advisory: This meeting will be conducted exclusively through videoconference and teleconference.

    [PAGE 2]
    1. Corridors Zoning Update
    Vote: All Ayes.
    2. San Pablo Avenue Specific Plan
    Vote: All Ayes.
    """

    local_ai = LocalAI()
    items = local_ai.extract_agenda(text)
    titles = [it.get("title", "") for it in items]
    lowered = " ".join(titles).lower()

    assert any("corridors zoning update" in t.lower() for t in titles)
    assert any("san pablo avenue specific plan" in t.lower() for t in titles)
    assert "hybrid model" not in lowered
    assert "virtual attendance" not in lowered
    assert "attend this meeting" not in lowered
    assert "live captioned" not in lowered
    assert "b-tv" not in lowered
    assert "channel 33" not in lowered
    assert "internet video stream" not in lowered


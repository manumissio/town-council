from unittest.mock import MagicMock


def test_adjournment_alone_does_not_stop_segmentation():
    from pipeline.llm import LocalAI

    LocalAI._instance = None
    ai = LocalAI()
    ai.llm = MagicMock()
    ai.llm.return_value = {"choices": [{"text": "No parseable agenda output"}]}

    text = """
    [PAGE 1]
    1. Subject: Budget Update
    Adjournment
    2. Subject: Housing Ordinance
    """

    items = ai.extract_agenda(text)
    titles = [it.get("title", "").lower() for it in items]
    assert any("budget update" in t for t in titles)
    assert any("housing ordinance" in t for t in titles)


def test_adjournment_plus_attestation_cluster_stops_segmentation():
    from pipeline.llm import LocalAI

    LocalAI._instance = None
    ai = LocalAI()
    ai.llm = MagicMock()
    ai.llm.return_value = {"choices": [{"text": "No parseable agenda output"}]}

    text = """
    [PAGE 1]
    1. Subject: Budget Update
    Adjournment
    ATTEST:
    IN WITNESS WHEREOF
    Date: January 21, 2021
    City Clerk

    [PAGE 2]
    2. Subject: Should Not Appear
    """

    items = ai.extract_agenda(text)
    titles = [it.get("title", "").lower() for it in items]
    joined = " ".join(titles)
    assert any("budget update" in t for t in titles)
    assert "should not appear" not in joined

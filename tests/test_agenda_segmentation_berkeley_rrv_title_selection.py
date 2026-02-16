from unittest.mock import MagicMock


def test_berkeley_rrv_keeps_city_council_referral_title_and_rejects_levine_notice():
    from pipeline.llm import LocalAI

    LocalAI._instance = None
    ai = LocalAI()
    ai.llm = MagicMock()
    ai.llm.return_value = {"choices": [{"text": "No parseable agenda output"}]}

    text = """
    [PAGE 1]
    Government Code Section 84308 (Levine Act) - Parties to a proceeding involving a license, permit, or other

    [PAGE 2]
    1.  2026 City Council Referral Prioritization Results Using Re-Weighted Range
    Voting (RRV)
    Recommendation: Review the completed Re-Weighted Range Voting (RRV) rankings.
    Adjournment
    ATTEST:
    IN WITNESS WHEREOF
    """

    items = ai.extract_agenda(text)
    titles = [it.get("title", "").lower() for it in items]
    joined = " ".join(titles)
    assert any("2026 city council referral prioritization results using re-weighted range voting" in t for t in titles)
    assert "government code section 84308" not in joined
    assert "levine act" not in joined

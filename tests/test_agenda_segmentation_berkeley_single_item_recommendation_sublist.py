from unittest.mock import MagicMock


def test_berkeley_special_agenda_keeps_single_top_level_item():
    from pipeline.llm import LocalAI

    LocalAI._instance = None
    ai = LocalAI()
    ai.llm = MagicMock()
    ai.llm.return_value = {"choices": [{"text": "No parseable agenda output"}]}

    text = """
    [PAGE 2]
    Action Calendar – Public Hearing
    1.
    Referral Response: Zoning Ordinance Amendments that Reform Residential Off-Street Parking
    Recommendation: Conduct a public hearing and upon conclusion select among proposed ordinance language options and take the following action:
    Adopt first reading of an Ordinance amending Berkeley Municipal Code Title 14 and Title 23 which would:
    1. Modify Minimum Residential Off-street Parking Requirements
    2. Impose Residential Parking Maximums in Transit-rich Areas
    3. Amend the Residential Preferential Parking (RPP) Permit Program
    4. Institute Transportation Demand Management (TDM) Requirements
    Financial Implications: See report
    Contact: Jordan Klein, Planning and Development
    Adjournment
    I hereby request that the City Clerk cause personal notice to be given.
    IN WITNESS WHEREOF

    [PAGE 3]
    ATTEST:
    Date: January 21, 2021
    Mark Numainville, City Clerk
    """

    items = ai.extract_agenda(text)
    titles = [it.get("title", "") for it in items]
    assert len(items) == 1
    assert "Referral Response: Zoning Ordinance Amendments" in titles[0]

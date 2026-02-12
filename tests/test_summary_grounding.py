from pipeline.summary_quality import is_summary_grounded


def test_summary_grounding_rejects_unsupported_claims():
    source = "Agenda"
    summary = "* CALL TO ORDER\n* ROLL CALL\n* CEREMONIAL MATTERS AND PRESENTATIONS"
    grounded = is_summary_grounded(summary, source)
    assert grounded.is_grounded is False
    assert grounded.unsupported_claims


def test_summary_grounding_accepts_supported_claims():
    source = """
    Call to order.
    Roll call.
    Ceremonial matters and presentations.
    Vote: All Ayes.
    """
    summary = "* Call to order\n* Roll call\n* Ceremonial matters and presentations"
    grounded = is_summary_grounded(summary, source)
    assert grounded.is_grounded is True
    assert grounded.coverage >= 0.45

import pytest

from pipeline.vote_extractor import parse_vote_extraction_response


def test_parse_vote_extraction_valid_json():
    raw = """
    {
      "outcome_label": "passed",
      "motion_text": "Adopt staff recommendation",
      "vote_tally_raw": "Ayes: 5, Noes: 0",
      "yes_count": 5,
      "no_count": 0,
      "abstain_count": null,
      "absent_count": null,
      "confidence": 0.92,
      "evidence_snippet": "Motion carried with ayes 5 and noes 0."
    }
    """
    parsed = parse_vote_extraction_response(raw, council_size=7)
    assert parsed.outcome_label == "passed"
    assert parsed.yes_count == 5
    assert parsed.no_count == 0
    assert parsed.confidence == pytest.approx(0.92)


def test_parse_vote_extraction_rejects_malformed_json():
    with pytest.raises(ValueError):
        parse_vote_extraction_response('{"outcome_label":"passed"')


def test_parse_vote_extraction_normalizes_synonyms():
    raw = """
    {"outcome_label":"approved unanimously","motion_text":null,"vote_tally_raw":null,
    "yes_count":null,"no_count":null,"abstain_count":null,"absent_count":null,
    "confidence":0.88,"evidence_snippet":null}
    """
    parsed = parse_vote_extraction_response(raw)
    assert parsed.outcome_label == "passed"


def test_parse_vote_extraction_rejects_impossible_tally():
    raw = """
    {"outcome_label":"passed","motion_text":null,"vote_tally_raw":"5-0",
    "yes_count":5,"no_count":0,"abstain_count":0,"absent_count":0,
    "confidence":0.8,"evidence_snippet":null}
    """
    with pytest.raises(ValueError):
        parse_vote_extraction_response(raw, council_size=4)

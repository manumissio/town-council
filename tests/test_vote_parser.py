import pytest
from pipeline.ground_truth_sync import GroundTruthSync

@pytest.fixture
def sync():
    return GroundTruthSync()

def test_parse_simple_vote(sync):
    text = "The motion carried with the following vote: Ayes: 5, Noes: 0."
    votes = sync.parse_votes(text)
    assert votes["result"] == "carried"

def test_parse_member_names(sync):
    text = "The motion carried with the following vote: Ayes: Mohan, Fruen, Chao, Moore, and Wei. Noes: None. Abstain: None. Absent: None."
    votes = sync.parse_votes(text)
    assert votes["result"] == "carried"
    assert "Mohan" in votes["ayes"]
    assert "Wei" in votes["ayes"]
    assert len(votes["ayes"]) == 5
    assert len(votes["noes"]) == 0

def test_parse_failed_motion(sync):
    text = "The motion failed with the following vote: Ayes: Moore. Noes: Mohan, Fruen, Chao, Wei."
    votes = sync.parse_votes(text)
    assert votes["result"] == "failed"
    assert votes["ayes"] == ["Moore"]
    assert len(votes["noes"]) == 4

def test_parse_varied_spacing(sync):
    text = "Adopted. Ayes:Mohan,Fruen. Noes : None"
    votes = sync.parse_votes(text)
    assert votes["result"] == "adopted"
    assert votes["ayes"] == ["Mohan", "Fruen"]

def test_parse_complex_names(sync):
    text = "Ayes: J.R. Fruen, Liang-Fang 'Liang' Chao, and R 'Ray' Wang."
    votes = sync.parse_votes(text)
    assert "J.R. Fruen" in votes["ayes"]
    assert "Liang-Fang 'Liang' Chao" in votes["ayes"]
    assert "R 'Ray' Wang" in votes["ayes"]

def test_parse_no_result(sync):
    text = "Item was presented."
    votes = sync.parse_votes(text)
    assert votes["result"] is None
    assert len(votes["ayes"]) == 0
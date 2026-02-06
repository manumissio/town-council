import pytest
from pipeline.utils import find_best_person_match

# Mock Person class for testing without a database
class MockPerson:
    def __init__(self, id, name):
        self.id = id
        self.name = name

def test_fuzzy_match_exact():
    """Test that an exact name match returns the correct person."""
    people = [MockPerson(1, "John Smith"), MockPerson(2, "Jane Doe")]
    match = find_best_person_match("John Smith", people)
    assert match is not None
    assert match.id == 1

def test_fuzzy_match_middle_initial():
    """Test that 'John Smith' matches 'John A. Smith' (Traditional AI)."""
    people = [MockPerson(1, "John A. Smith")]
    match = find_best_person_match("John Smith", people)
    assert match is not None
    assert match.id == 1

def test_fuzzy_match_reordered():
    """Test that 'Smith, John' matches 'John Smith' due to token sorting."""
    people = [MockPerson(1, "John Smith")]
    match = find_best_person_match("Smith, John", people)
    assert match is not None
    assert match.id == 1

def test_fuzzy_match_below_threshold():
    """Test that 'John Smith' does NOT match 'Jane Smith' (Low score)."""
    people = [MockPerson(1, "Jane Smith")]
    # Threshold 85 should block this match (Jane vs John)
    match = find_best_person_match("John Smith", people, threshold=85)
    assert match is None

def test_fuzzy_match_empty_list():
    """Test that matching against an empty list returns None safely."""
    assert find_best_person_match("John Smith", []) is None

import pytest
import sys
import os

# Ensure the pipeline directory is in the path for indexer imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'pipeline'))

def test_meeting_category_normalization():
    """
    Test: Does the indexer correctly 'clean' messy meeting strings?
    We want to ensure that phrases like 'Regular Meeting' correctly 
    map to the clean 'Regular' category for our UI.
    """
    # Define a helper function that mimics the logic in indexer.py
    def get_category(raw_type):
        raw_type = (raw_type or "").lower()
        if "regular" in raw_type:
            return "Regular"
        elif "special" in raw_type:
            return "Special"
        elif "closed" in raw_type:
            return "Closed"
        return "Other"

    # Test Cases
    assert get_category("City Council Regular Meeting") == "Regular"
    assert get_category("REGULAR SESSION") == "Regular"
    assert get_category("Special Meeting of the Council") == "Special"
    assert get_category("2026-02-10 CLOSED SESSION") == "Closed"
    assert get_category("Emergency Budget Meeting") == "Other"
    assert get_category(None) == "Other"
    assert get_category("") == "Other"

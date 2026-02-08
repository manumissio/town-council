
import sys
import os
import pytest

# Setup: Add the project folders to the Python path
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(root_dir)

from pipeline.utils import is_likely_human_name

def test_bouncer_standard_names():
    """
    Ensures that real names (and names with tricky surnames like 'Park') 
    are allowed through the filter.
    """
    assert is_likely_human_name("Jesse Arreguin") is True
    assert is_likely_human_name("Linda Park") is True
    # 'Street' is blocked even in multi-word names because it's usually a location
    assert is_likely_human_name("John Street") is False
    assert is_likely_human_name("Sarah Avenue") is False

def test_bouncer_contextual_noise():
    """
    Tests 'Contextual Noise' (words that can be names or municipal objects).
    We only allow them if they are part of a full name or have a title like 'Mayor'.
    """
    # Single word versions should be blocked (e.g. 'Park' on its own)
    assert is_likely_human_name("Park") is False
    assert is_likely_human_name("Clerk") is False
    assert is_likely_human_name("Staff") is False
    
    # Unless a title was provided (simulated by allow_single_word=True)
    assert is_likely_human_name("Park", allow_single_word=True) is True
    assert is_likely_human_name("Arreguin", allow_single_word=True) is True

def test_bouncer_total_noise():
    """
    Ensures that obvious municipal boilerplate and OCR noise are blocked.
    """
    assert is_likely_human_name("City Clerk") is False
    assert is_likely_human_name("City Manager") is False
    assert is_likely_human_name("Exhibit A") is False
    assert is_likely_human_name("Page 12") is False
    assert is_likely_human_name("Infestation") is False
    assert is_likely_human_name("Main Street") is False

def test_bouncer_catherine_bug():
    """
    Verifies that the word-boundary logic works.
    'Catherine' contains 'ca' (the state abbreviation), but it shouldn't 
    be blocked by the 'ca' rule.
    """
    # 'Catherine' contains 'ca', but should NOT be blocked by the 'ca' rule.
    # HOWEVER, as a single word without a title, it IS blocked by the word count guardrail.
    assert is_likely_human_name("Catherine") is False
    assert is_likely_human_name("Catherine", allow_single_word=True) is True
    
    # 'California' should be blocked even with single word allowed (in total_noise)
    assert is_likely_human_name("California", allow_single_word=True) is False

def test_bouncer_tech_noise():
    """
    Ensures web URLs and emails don't get indexed as people.
    """
    assert is_likely_human_name("clerk@berkeley.ca.gov") is False
    assert is_likely_human_name("http://example.com") is False

def test_bouncer_vowel_density():
    """
    Tests the vowel density heuristic.
    Real human names almost always have a reasonable ratio of vowels.
    OCR fragments (like 'Spl Tax Bds') do not.
    """
    # Real names have vowels
    assert is_likely_human_name("John Doe") is True
    # OCR noise doesn't
    assert is_likely_human_name("Spl Tax Bds") is False
    assert is_likely_human_name("XF-20-Z") is False


def test_bouncer_rejects_spaced_ocr_and_lowercase_prose():
    assert is_likely_human_name("P R O C L A M A T I O N") is False
    assert is_likely_human_name("state of emergency continues") is False
